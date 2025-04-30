from typing import Optional
import uuid
import boto3
from abc import ABC, abstractmethod
from botocore.exceptions import ClientError
from models import Document  # src/models.py から Document をインポート


class DocumentRepository(ABC):
    """
    ドキュメントのデータ永続化を担当するリポジトリの抽象基底クラス。
    """

    @abstractmethod
    def save_or_update(self, document: Document) -> str:
        """
        企画ドキュメントを永続化ストレージに保存または更新します。

        Args:
            document: 保存または更新するDocumentオブジェクト。

        Returns:
            保存または更新されたドキュメントのID。

        Raises:
            Exception: 永続化処理中にエラーが発生した場合。
        """
        pass

    @abstractmethod
    def get_by_id(self, project_id: str) -> Optional[Document]:
        """
        指定されたIDに基づいてドキュメントを取得します。

        Args:
            project_id: 取得するドキュメントのID。

        Returns:
            見つかった場合はDocumentオブジェクト、見つからない場合はNone。

        Raises:
            Exception: 取得処理中にエラーが発生した場合。
        """
        pass


class PlanDocumentRepository(DocumentRepository):
    """
    企画ドキュメントのデータ永続化を担当する抽象リポジトリクラス。
    """

    pass


class TechSpecDocumentRepository(DocumentRepository):
    """
    技術仕様書のデータ永続化を担当する抽象リポジトリクラス。
    """

    pass


class DynamoDbDocumentRepository(
    PlanDocumentRepository,
    TechSpecDocumentRepository,
):
    """
    DynamoDBを使用して企画ドキュメントのデータ永続化を担当する具象リポジトリクラス。
    """

    def __init__(self, table_name: str, dynamodb_resource=None):  # デフォルト引数を追加
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
        self._table = self._dynamodb.Table(table_name)

    def initialize_table(self):
        """
        DynamoDBテーブルが存在しない場合に作成します。
        アプリケーション起動時に呼び出すことを想定しています。
        """
        try:
            # テーブル名をクラス変数から取得
            table = self._dynamodb.create_table(
                TableName=self.TABLE_NAME,
                KeySchema=[
                    {"AttributeName": "project_id", "KeyType": "HASH"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "project_id", "AttributeType": "S"},
                ],
                ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            )
            print(f"Table '{self.TABLE_NAME}' created successfully.")
            # テーブルが利用可能になるまで待機
            table.wait_until_exists()
            print(f"Table '{self.TABLE_NAME}' is now active.")
            self._table = table  # 作成したテーブルオブジェクトをインスタンス変数に設定
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceInUseException":
                print(f"Table '{self.TABLE_NAME}' already exists.")
                # 既存のテーブルオブジェクトを取得
                self._table = self._dynamodb.Table(self.TABLE_NAME)
            else:
                print(f"Error creating table: {e}")
                raise

    def save_or_update(self, document: Document) -> str:
        """
        企画ドキュメントをDynamoDBに保存または更新します。

        Args:
            document: 保存または更新するDocumentオブジェクト。

        Returns:
            保存または更新されたドキュメントのID。

        Raises:
            Exception: DynamoDBへの書き込み中にエラーが発生した場合。
        """
        project_id = document.project_id
        if project_id is None:
            # 新規作成の場合はUUIDを生成
            project_id = str(uuid.uuid4())
            document.project_id = (
                project_id  # 生成したIDをドキュメントオブジェクトにも設定
            )

        try:
            self._table.put_item(
                Item={"project_id": project_id, "content": document.content}
            )
            return project_id
        except ClientError as e:
            print(f"Error saving/updating document (ID: {project_id}): {e}")
            raise Exception(
                f"Failed to save/update document: {e.response['Error']['Message']}"
            ) from e

    def get_by_id(self, project_id: str) -> Optional[Document]:
        """
        指定されたIDに基づいてドキュメントをDynamoDBから取得します。

        Args:
            project_id: 取得するドキュメントのID。

        Returns:
            見つかった場合はDocumentオブジェクト、見つからない場合はNone。

        Raises:
            Exception: DynamoDBからの読み取り中にエラーが発生した場合。
        """
        try:
            response = self._table.get_item(Key={"project_id": project_id})
            item = response.get("Item")
            if item:
                return Document(
                    project_id=item["project_id"],
                    content=item["content"],
                )
            else:
                return None
        except ClientError as e:
            print(f"Error getting document (ID: {project_id}): {e}")
            raise Exception(
                f"Failed to get document: {e.response['Error']['Message']}"
            ) from e
