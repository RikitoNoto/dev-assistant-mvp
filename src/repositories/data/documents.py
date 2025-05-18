from __future__ import annotations
from typing import Optional, Dict, Any, List
from datetime import datetime
import boto3
from abc import ABC, abstractmethod
from botocore.exceptions import ClientError


class DocumentRepository(ABC):
    """
    ドキュメントのデータ永続化を担当するリポジトリの抽象基底クラス。
    """

    @abstractmethod
    def initialize(self, *args, **kwargs):
        """
        リポジトリを初期化します。
        具体的な実装に応じて、必要な初期化処理を行います。
        """
        pass

    @abstractmethod
    def save_or_update(self, document_data: Dict[str, Any]) -> str:
        """
        企画ドキュメントを永続化ストレージに保存または更新します。

        Args:
            document_data: 保存または更新するドキュメントデータの辞書。

        Returns:
            保存または更新されたドキュメントのID。

        Raises:
            Exception: 永続化処理中にエラーが発生した場合。
        """
        pass

    @abstractmethod
    def get_by_id(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        指定されたIDに基づいてドキュメントを取得します。

        Args:
            project_id: 取得するドキュメントのID。

        Returns:
            見つかった場合はドキュメントデータの辞書、見つからない場合はNone。

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

    def initialize(self, table_name: str):
        """
        DynamoDBテーブルが存在しない場合に作成します。
        アプリケーション起動時に呼び出すことを想定しています。
        """
        try:
            # テーブル名をクラス変数から取得
            table = self._dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {"AttributeName": "project_id", "KeyType": "HASH"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "project_id", "AttributeType": "S"},
                ],
                ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            )
            print(f"Table '{table_name}' created successfully.")
            # テーブルが利用可能になるまで待機
            table.wait_until_exists()
            print(f"Table '{table_name}' is now active.")
            self._table = table  # 作成したテーブルオブジェクトをインスタンス変数に設定
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceInUseException":
                print(f"Table '{table_name}' already exists.")
                # 既存のテーブルオブジェクトを取得
                self._table = self._dynamodb.Table(table_name)
            else:
                print(f"Error creating table: {e}")
                raise

    def save_or_update(self, document_data: Dict[str, Any]) -> str:
        """
        企画ドキュメントをDynamoDBに保存または更新します。

        Args:
            document_data: 保存または更新するドキュメントデータの辞書。

        Returns:
            保存または更新されたドキュメントのID。

        Raises:
            Exception: DynamoDBへの書き込み中にエラーが発生した場合。
        """
        # project_id は辞書に必ず含まれるため、None チェックは不要
        project_id = document_data["project_id"]

        try:
            # created_atとupdated_atはISO形式の文字列として保存
            item = {
                "project_id": project_id,
                "document_id": document_data["document_id"],
                "content": document_data["content"],
                "created_at": document_data["created_at"],
                "updated_at": document_data["updated_at"]
            }
            
            self._table.put_item(Item=item)
            return project_id
        except ClientError as e:
            print(f"Error saving/updating document (ID: {project_id}): {e}")
            raise Exception(
                f"Failed to save/update document: {e.response['Error']['Message']}"
            ) from e

    def get_by_id(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        指定されたIDに基づいてドキュメントをDynamoDBから取得します。

        Args:
            project_id: 取得するドキュメントのID。

        Returns:
            見つかった場合はドキュメントデータの辞書、見つからない場合はNone。

        Raises:
            Exception: DynamoDBからの読み取り中にエラーが発生した場合。
        """
        try:
            response = self._table.get_item(Key={"project_id": project_id})
            item = response.get("Item")
            if item:
                # created_atとupdated_atが存在しない場合は現在時刻をISO形式で設定
                if "created_at" not in item:
                    item["created_at"] = datetime.now().isoformat()
                if "updated_at" not in item:
                    item["updated_at"] = datetime.now().isoformat()
                if "document_id" not in item:
                    item["document_id"] = item["project_id"]
                    
                return item
            else:
                return None
        except ClientError as e:
            print(f"Error getting document (ID: {project_id}): {e}")
            raise Exception(
                f"Failed to get document: {e.response['Error']['Message']}"
            ) from e
