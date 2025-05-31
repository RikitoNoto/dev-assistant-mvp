from __future__ import annotations
from typing import Optional, List, Dict, Any
import boto3
from abc import ABC, abstractmethod
from botocore.exceptions import ClientError

class IssueRepository(ABC):
    """
    Issueのデータ永続化を担当するリポジトリの抽象基底クラス。
    """

    @abstractmethod
    def initialize(self, *args, **kwargs):
        """
        リポジトリを初期化します。
        具体的な実装に応じて、必要な初期化処理を行います。
        """
        pass

    @abstractmethod
    def save_or_update(self, issue_data: Dict[str, Any]) -> str:
        """
        Issueを永続化ストレージに保存または更新します。

        Args:
            issue_data: 保存または更新するIssueデータの辞書。

        Returns:
            保存または更新されたIssueのID。

        Raises:
            Exception: 永続化処理中にエラーが発生した場合。
        """
        pass

    @abstractmethod
    def get_by_id(self, project_id: str, issue_id: str) -> Optional[Dict[str, Any]]:
        """
        指定されたIDに基づいてIssueを取得します。

        Args:
            project_id: Issueが属するプロジェクトのID。
            issue_id: 取得するIssueのID。

        Returns:
            見つかった場合はIssueデータの辞書、見つからない場合はNone。

        Raises:
            Exception: 取得処理中にエラーが発生した場合。
        """
        pass

    @abstractmethod
    def get_by_project_id(self, project_id: str) -> List[Dict[str, Any]]:
        """
        指定されたプロジェクトIDに属する全てのIssueを取得します。

        Args:
            project_id: Issueが属するプロジェクトのID。

        Returns:
            Issueデータの辞書のリスト。

        Raises:
            Exception: 取得処理中にエラーが発生した場合。
        """
        pass

    @abstractmethod
    def delete(self, project_id: str, issue_id: str) -> None:
        """
        指定されたIDのIssueを削除します。

        Args:
            project_id: Issueが属するプロジェクトのID。
            issue_id: 削除するIssueのID。

        Raises:
            Exception: 削除処理中にエラーが発生した場合。
        """
        pass


class DynamoDbIssueRepository(IssueRepository):
    """
    DynamoDBを使用してIssueのデータ永続化を担当する具象リポジトリクラス。
    """

    def __init__(self, table_name: str, dynamodb_resource=None):
        if dynamodb_resource:
            self._dynamodb = dynamodb_resource
        else:
            # 環境変数からDynamoDB設定を取得
            from config import DYNAMODB_ENDPOINT, AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
            self._dynamodb = boto3.resource(
                "dynamodb",
                endpoint_url=DYNAMODB_ENDPOINT,
                region_name=AWS_REGION,
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            )
        self._table_name = table_name  # table_nameをインスタンス変数として保存
        self._table = self._dynamodb.Table(table_name)

    def initialize(self):
        """
        DynamoDBテーブルが存在しない場合に作成します。
        """
        try:
            table = self._dynamodb.create_table(
                TableName=self._table_name,
                KeySchema=[
                    {
                        "AttributeName": "project_id",
                        "KeyType": "HASH",
                    },  # パーティションキー
                    {"AttributeName": "issue_id", "KeyType": "RANGE"},  # ソートキー
                ],
                AttributeDefinitions=[
                    {"AttributeName": "project_id", "AttributeType": "S"},
                    {"AttributeName": "issue_id", "AttributeType": "S"},
                ],
                ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            )
            print(f"Table '{self._table_name}' created successfully.")
            table.wait_until_exists()
            print(f"Table '{self._table_name}' is now active.")
            self._table = table
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceInUseException":
                print(f"Table '{self._table_name}' already exists.")
                self._table = self._dynamodb.Table(self._table_name)
            else:
                print(f"Error creating table: {e}")
                raise

    def save_or_update(self, issue_data: Dict[str, Any]) -> str:
        """
        IssueをDynamoDBに保存または更新します。
        """
        try:
            # created_atとupdated_atがdatetimeオブジェクトの場合、ISO形式の文字列に変換
            item = issue_data.copy()
            if 'created_at' in item and hasattr(item['created_at'], 'isoformat'):
                item['created_at'] = item['created_at'].isoformat()
            if 'updated_at' in item and hasattr(item['updated_at'], 'isoformat'):
                item['updated_at'] = item['updated_at'].isoformat()
                
            self._table.put_item(Item=item)
            return issue_data['issue_id']
        except ClientError as e:
            print(f"Error saving/updating issue (ID: {issue_data['issue_id']}): {e}")
            raise Exception(
                f"Failed to save/update issue: {e.response['Error']['Message']}"
            ) from e

    def get_by_id(self, project_id: str, issue_id: str) -> Optional[Dict[str, Any]]:
        """
        指定されたIDに基づいてIssueをDynamoDBから取得します。
        """
        try:
            # Ensure both keys are strings for DynamoDB
            project_id_str = str(project_id)
            issue_id_str = str(issue_id)
            
            response = self._table.get_item(
                Key={
                    "project_id": project_id_str,
                    "issue_id": issue_id_str
                }
            )
            item = response.get("Item")
            return item
        except ClientError as e:
            print(f"Error getting issue (Project ID: {project_id}, Issue ID: {issue_id}): {e}")
            raise Exception(
                f"Failed to get issue: {e.response['Error']['Message']}"
            ) from e

    def get_by_project_id(self, project_id: str) -> List[Dict[str, Any]]:
        """
        指定されたプロジェクトIDに属する全てのIssueをDynamoDBから取得します。
        """
        try:
            response = self._table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key("project_id").eq(
                    project_id
                )
            )
            items = response.get("Items", [])
            return items
        except ClientError as e:
            print(f"Error getting issues for project (ID: {project_id}): {e}")
            raise Exception(
                f"Failed to get issues for project: {e.response['Error']['Message']}"
            ) from e

    def delete(self, project_id: str, issue_id: str) -> None:
        """
        指定されたIDのIssueをDynamoDBから削除します。
        """
        try:
            self._table.delete_item(
                Key={"project_id": project_id, "issue_id": issue_id}
            )
        except ClientError as e:
            print(f"Error deleting issue (ID: {issue_id}): {e}")
            raise Exception(
                f"Failed to delete issue: {e.response['Error']['Message']}"
            ) from e
