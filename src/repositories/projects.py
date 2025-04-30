from typing import Optional, List
import boto3
from abc import ABC, abstractmethod
from botocore.exceptions import ClientError
from models import Project
from uuid import UUID
from datetime import datetime


class ProjectRepository(ABC):
    """
    プロジェクトのデータ永続化を担当するリポジトリの抽象基底クラス。
    """

    @abstractmethod
    def initialize(self, *args, **kwargs):
        """
        リポジトリを初期化します。
        具体的な実装に応じて、必要な初期化処理を行います。
        """
        pass

    @abstractmethod
    def save_or_update(self, project: Project) -> UUID:
        """
        プロジェクトを永続化ストレージに保存または更新します。

        Args:
            project: 保存または更新するProjectオブジェクト。

        Returns:
            保存または更新されたプロジェクトのID。

        Raises:
            Exception: 永続化処理中にエラーが発生した場合。
        """
        pass

    @abstractmethod
    def get_by_id(self, project_id: UUID) -> Optional[Project]:
        """
        指定されたIDに基づいてプロジェクトを取得します。

        Args:
            project_id: 取得するプロジェクトのID。

        Returns:
            見つかった場合はProjectオブジェクト、見つからない場合はNone。

        Raises:
            Exception: 取得処理中にエラーが発生した場合。
        """
        pass

    @abstractmethod
    def get_all(self) -> List[Project]:
        pass
        """
        すべてのプロジェクトを取得します。

        Returns:
            プロジェクトのリスト。

        Raises:
            Exception: 取得処理中にエラーが発生した場合。
        """
        pass

    @abstractmethod
    def delete_by_id(self, project_id: UUID) -> bool:
        """
        指定されたIDに基づいてプロジェクトを削除します。

        Args:
            project_id: 削除するプロジェクトのID。

        Returns:
            削除が成功した場合はTrue、失敗した場合はFalse。

        Raises:
            Exception: 削除処理中にエラーが発生した場合。
        """
        pass


class DynamoDbProjectRepository(ProjectRepository):
    """
    DynamoDBを使用してプロジェクトのデータ永続化を担当する具象リポジトリクラス。
    """

    def __init__(self, dynamodb_resource=None):
        """
        リポジトリを初期化します。
        外部からDynamoDBリソースを注入できるようにします（テスト容易性のため）。
        指定されない場合は、デフォルト設定で新しいリソースを作成します。
        """
        if dynamodb_resource:
            self._dynamodb = dynamodb_resource
        else:
            # デフォルトのDynamoDB Local設定
            self._dynamodb = boto3.resource(
                "dynamodb",
                endpoint_url="http://localhost:8000",
                region_name="us-west-2",
                aws_access_key_id="dummy",
                aws_secret_access_key="dummy",
            )
        # テーブルオブジェクトの初期化は initialize で行う
        self._table = None

    def initialize(self, table_name: str):
        """
        DynamoDBテーブルが存在しない場合に作成します。
        アプリケーション起動時に呼び出すことを想定しています。
        """
        try:
            table = self._dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {"AttributeName": "project_id", "KeyType": "HASH"},
                ],
                AttributeDefinitions=[
                    {
                        "AttributeName": "project_id",
                        "AttributeType": "S",
                    },  # UUIDは文字列として保存
                ],
                ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            )
            print(f"Table '{table_name}' created successfully.")
            table.wait_until_exists()
            print(f"Table '{table_name}' is now active.")
            self._table = table
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceInUseException":
                print(f"Table '{table_name}' already exists.")
                self._table = self._dynamodb.Table(table_name)
            else:
                print(f"Error creating table: {e}")
                raise

    def _ensure_table_initialized(self):
        """テーブルが初期化されていることを確認します。"""
        if self._table is None:
            # 通常は initialize が呼ばれるが、念のため
            print("Table was not initialized. Initializing now.")
            self.initialize()

    def save_or_update(self, project: Project) -> UUID:
        """
        プロジェクトをDynamoDBに保存または更新します。

        Args:
            project: 保存または更新するProjectオブジェクト。

        Returns:
            保存または更新されたプロジェクトのID。

        Raises:
            Exception: DynamoDBへの書き込み中にエラーが発生した場合。
        """
        self._ensure_table_initialized()
        project.updated_at = datetime.now()  # 更新日時を現在時刻に設定
        try:
            # UUIDとdatetimeを文字列に変換して保存
            item_to_save = {
                "project_id": str(project.project_id),
                "title": project.title,
                "created_at": project.created_at.isoformat(),
                "updated_at": project.updated_at.isoformat(),
            }
            self._table.put_item(Item=item_to_save)
            return project.project_id
        except ClientError as e:
            print(f"Error saving/updating project (ID: {project.project_id}): {e}")
            raise Exception(
                f"Failed to save/update project: {e.response['Error']['Message']}"
            ) from e

    def get_by_id(self, project_id: UUID) -> Optional[Project]:
        """
        指定されたIDに基づいてプロジェクトをDynamoDBから取得します。

        Args:
            project_id: 取得するプロジェクトのID。

        Returns:
            見つかった場合はProjectオブジェクト、見つからない場合はNone。

        Raises:
            Exception: DynamoDBからの読み取り中にエラーが発生した場合。
        """
        self._ensure_table_initialized()
        try:
            response = self._table.get_item(Key={"project_id": str(project_id)})
            item = response.get("Item")
            if item:
                # 文字列からUUIDとdatetimeに変換して返す
                return Project(
                    project_id=UUID(item["project_id"]),
                    title=item["title"],
                    created_at=datetime.fromisoformat(item["created_at"]),
                    updated_at=datetime.fromisoformat(item["updated_at"]),
                )
            else:
                return None
        except ClientError as e:
            print(f"Error getting project (ID: {project_id}): {e}")
            raise Exception(
                f"Failed to get project: {e.response['Error']['Message']}"
            ) from e
        except ValueError as e:  # UUIDやdatetimeの変換エラー
            print(f"Error converting data for project (ID: {project_id}): {e}")
            raise Exception(f"Data conversion error for project: {e}") from e

    def get_all(self) -> List[Project]:
        """
        すべてのプロジェクトをDynamoDBから取得します。

        Returns:
            プロジェクトのリスト。

        Raises:
            Exception: DynamoDBからの読み取り中にエラーが発生した場合。
        """
        self._ensure_table_initialized()
        projects = []
        try:
            response = self._table.scan()
            items = response.get("Items", [])
            for item in items:
                try:
                    # 文字列からUUIDとdatetimeに変換
                    projects.append(
                        Project(
                            project_id=UUID(item["project_id"]),
                            title=item["title"],
                            created_at=datetime.fromisoformat(item["created_at"]),
                            updated_at=datetime.fromisoformat(item["updated_at"]),
                        )
                    )
                except ValueError as e:
                    print(f"Skipping item due to conversion error: {item}, Error: {e}")
                    # エラーが発生した項目はスキップする

            # DynamoDBのscanは1MB制限があるため、ページネーションが必要な場合がある
            while "LastEvaluatedKey" in response:
                response = self._table.scan(
                    ExclusiveStartKey=response["LastEvaluatedKey"]
                )
                items = response.get("Items", [])
                for item in items:
                    try:
                        projects.append(
                            Project(
                                project_id=UUID(item["project_id"]),
                                title=item["title"],
                                created_at=datetime.fromisoformat(item["created_at"]),
                                updated_at=datetime.fromisoformat(item["updated_at"]),
                            )
                        )
                    except ValueError as e:
                        print(
                            f"Skipping item due to conversion error: {item}, Error: {e}"
                        )

            return projects
        except ClientError as e:
            print(f"Error getting all projects: {e}")
            raise Exception(
                f"Failed to get all projects: {e.response['Error']['Message']}"
            ) from e

    def delete_by_id(self, project_id: UUID) -> bool:
        """
        指定されたIDに基づいてプロジェクトをDynamoDBから削除します。

        Args:
            project_id: 削除するプロジェクトのID。

        Returns:
            削除が成功した場合はTrue。

        Raises:
            Exception: DynamoDBからの削除中にエラーが発生した場合。
            ValueError: 指定されたIDのプロジェクトが見つからない場合。
        """
        self._ensure_table_initialized()
        try:
            response = self._table.delete_item(
                Key={"project_id": str(project_id)},
                ReturnValues="ALL_OLD",  # 削除前のアイテムを取得して存在確認
            )
            # 'Attributes' がレスポンスに含まれていれば、アイテムが存在し削除されたことを意味する
            if "Attributes" in response:
                return True
            else:
                # アイテムが存在しなかった場合
                raise ValueError(f"Project with ID '{project_id}' not found.")
        except ClientError as e:
            print(f"Error deleting project (ID: {project_id}): {e}")
            raise Exception(
                f"Failed to delete project: {e.response['Error']['Message']}"
            ) from e
