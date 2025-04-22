import os
import httpx
import json
from typing import Optional, Dict, Any, List


class GitHubClient:
    """GitHub APIとやり取りするためのクライアントクラス"""

    def __init__(self, token: str, owner: str, repo: str):
        """
        GitHubClientを初期化します。

        Args:
            token: GitHub Personal Access Token (PAT).
            owner: リポジトリのオーナー名。
            repo: リポジトリ名。
        """
        if not token:
            raise ValueError("GitHub token is required.")
        if not owner:
            raise ValueError("Repository owner is required.")
        if not repo:
            raise ValueError("Repository name is required.")

        self._token = token
        self._owner = owner
        self._repo = repo
        self._base_url = "https://api.github.com"
        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",  # 推奨されるバージョン指定
        }
        # GraphQL API用のヘッダーも用意
        self._graphql_headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        self._graphql_url = f"{self._base_url}/graphql"

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        is_graphql: bool = False,
    ) -> Dict[str, Any]:
        """
        GitHub APIにリクエストを送信する共通メソッド。

        Args:
            method: HTTPメソッド (GET, POST, PATCH, etc.).
            endpoint: APIエンドポイント (e.g., /repos/{owner}/{repo}/issues).
            data: リクエストボディとして送信するデータ (JSON)。
            is_graphql: GraphQL APIを使用するかどうか。

        Returns:
            APIからのレスポンス (JSON)。

        Raises:
            httpx.HTTPStatusError: APIリクエストが失敗した場合。
            Exception: その他のエラーが発生した場合。
        """
        url = self._graphql_url if is_graphql else f"{self._base_url}{endpoint}"
        headers = self._graphql_headers if is_graphql else self._headers

        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method, url, headers=headers, json=data, timeout=30.0
                )
                response.raise_for_status()  # エラーがあれば例外を発生させる
                # レスポンスボディがない場合 (e.g., 204 No Content) は空の辞書を返す
                if response.status_code == 204:
                    return {}
                # レスポンスが空の場合も考慮
                if not response.content:
                    return {}
                return response.json()
            except httpx.HTTPStatusError as e:
                error_message = f"GitHub API Error ({e.response.status_code})"
                try:
                    # エラーレスポンスがJSON形式であれば詳細を追加
                    error_details = e.response.json()
                    error_message += f": {json.dumps(error_details)}"
                except json.JSONDecodeError:
                    # JSONでなければテキストとして追加
                    error_message += f": {e.response.text}"
                print(error_message)
                # エラーメッセージを含めて再raiseする
                raise httpx.HTTPStatusError(
                    message=error_message,
                    request=e.request,
                    response=e.response,
                ) from e
            except Exception as e:
                print(f"An unexpected error occurred during GitHub API request: {e}")
                raise

    async def create_issue(
        self, title: str, body: Optional[str] = None, labels: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        GitHubリポジトリに新しいIssueを作成します。

        Args:
            title: Issueのタイトル。
            body: Issueの本文。
            labels: Issueに付与するラベルのリスト。

        Returns:
            作成されたIssueの情報 (APIレスポンス)。
        """
        endpoint = f"/repos/{self._owner}/{self._repo}/issues"
        payload: Dict[str, Any] = {"title": title}  # 型ヒントを明確化
        if body:
            payload["body"] = body
        if labels:
            payload["labels"] = labels

        print(f"Creating issue '{title}' in {self._owner}/{self._repo}")
        return await self._request("POST", endpoint, data=payload)

    async def get_project_v2_id(self, project_number: int) -> Optional[str]:
        """
        指定されたプロジェクト番号に対応するProjectV2のNode IDを取得します。
        オーナーがユーザーまたはOrganizationのどちらでも動作するように試みます。

        Args:
            project_number: プロジェクトの番号。

        Returns:
            ProjectV2のNode ID。見つからない場合はNone。
        """
        # まずユーザーとして試す
        user_query = """
        query($owner: String!, $projectNumber: Int!) {
          user(login: $owner) {
            projectV2(number: $projectNumber) {
              id
            }
          }
        }
        """
        variables = {"owner": self._owner, "projectNumber": project_number}
        user_payload = {"query": user_query, "variables": variables}

        print(
            f"Attempting to fetch ProjectV2 ID for project number {project_number} as user '{self._owner}'"
        )
        try:
            response = await self._request(
                "POST", "", data=user_payload, is_graphql=True
            )
            project_data = response.get("data", {}).get("user", {}).get("projectV2")
            if project_data and "id" in project_data:
                project_id = project_data["id"]
                print(f"Found ProjectV2 ID (as user): {project_id}")
                return project_id
            # ユーザーとして見つからなかった場合、エラーが含まれているか確認
            elif response.get("errors"):
                print(f"GraphQL errors when fetching as user: {response['errors']}")
                # Organizationとして試行を続ける

        except httpx.HTTPStatusError as e:
            # 404などは想定内としてOrganization検索へ
            print(
                f"Fetching as user failed (HTTP {e.response.status_code}), trying as organization."
            )
        except Exception as e:
            print(f"Unexpected error fetching ProjectV2 ID as user: {e}")
            # 予期せぬエラーでもOrganizationとして試す価値はあるかもしれない

        # Organizationとして試す
        org_query = """
        query($owner: String!, $projectNumber: Int!) {
          organization(login: $owner) {
            projectV2(number: $projectNumber) {
              id
            }
          }
        }
        """
        org_payload = {"query": org_query, "variables": variables}
        print(
            f"Attempting to fetch ProjectV2 ID for project number {project_number} as organization '{self._owner}'"
        )
        try:
            org_response = await self._request(
                "POST", "", data=org_payload, is_graphql=True
            )
            org_project_data = (
                org_response.get("data", {}).get("organization", {}).get("projectV2")
            )
            if org_project_data and "id" in org_project_data:
                project_id = org_project_data["id"]
                print(f"Found ProjectV2 ID (as organization): {project_id}")
                return project_id
            else:
                # Organizationとしても見つからなかった場合
                errors = org_response.get("errors")
                if errors:
                    print(f"GraphQL errors when fetching as organization: {errors}")
                else:
                    print(
                        f"ProjectV2 with number {project_number} not found for owner '{self._owner}' (checked as user and organization). Response: {org_response}"
                    )
                return None
        except httpx.HTTPStatusError as e:
            print(
                f"Fetching as organization failed (HTTP {e.response.status_code}). Project not found or access issue."
            )
            return None
        except Exception as e:
            print(f"Unexpected error fetching ProjectV2 ID as organization: {e}")
            return None

    async def add_issue_to_project_v2(
        self, project_id: str, issue_node_id: str
    ) -> Optional[str]:
        """
        指定されたProjectV2にIssueを追加します。

        Args:
            project_id: 追加先のProjectV2のNode ID。
            issue_node_id: 追加するIssueのNode ID。

        Returns:
            追加されたプロジェクトアイテムのID。失敗した場合はNone。
        """
        mutation = """
        mutation($projectId: ID!, $contentId: ID!) {
          addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
            item {
              id
            }
          }
        }
        """
        variables = {"projectId": project_id, "contentId": issue_node_id}
        payload = {"query": mutation, "variables": variables}

        print(
            f"Adding issue (Node ID: {issue_node_id}) to project (Node ID: {project_id})"
        )
        try:
            response = await self._request("POST", "", data=payload, is_graphql=True)
            # エラーチェックを先に行う
            errors = response.get("errors")
            if errors:
                print(f"Failed to add issue to project. GraphQL Errors: {errors}")
                return None

            item_data = (
                response.get("data", {}).get("addProjectV2ItemById", {}).get("item")
            )
            if item_data and "id" in item_data:
                item_id = item_data["id"]
                print(f"Successfully added issue to project. Item ID: {item_id}")
                return item_id
            else:
                # データ構造が予期しない場合
                print(
                    f"Failed to add issue to project. Unexpected response structure: {response}"
                )
                return None
        except httpx.HTTPStatusError as e:
            # HTTPレベルのエラーもここでキャッチ
            print(f"Failed to add issue to project due to HTTP error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error adding issue to project: {e}")
            return None


# --- 以下、テスト用のコード (本番利用時は削除またはコメントアウト) ---
async def _main_test():
    # 環境変数から設定を読み込む
    from dotenv import load_dotenv

    load_dotenv()  # .envファイルを読み込む
    github_token = os.getenv("GITHUB_PAT")
    github_owner = os.getenv("GITHUB_OWNER")
    github_repo = os.getenv("GITHUB_REPO")
    project_number_str = os.getenv("GITHUB_PROJECT_NUMBER")

    if not all([github_token, github_owner, github_repo, project_number_str]):
        print(
            "必要な環境変数 (GITHUB_PAT, GITHUB_OWNER, GITHUB_REPO, GITHUB_PROJECT_NUMBER) が設定されていません。"
        )
        return

    try:
        project_number = int(project_number_str)
    except ValueError:
        print("GITHUB_PROJECT_NUMBER は整数である必要があります。")
        return

    client = GitHubClient(token=github_token, owner=github_owner, repo=github_repo)

    try:
        # 1. プロジェクトIDを取得
        print("\n--- 1. Fetching Project ID ---")
        project_id = await client.get_project_v2_id(project_number)
        if not project_id:
            print("プロジェクトIDの取得に失敗しました。処理を終了します。")
            return
        print(f"Project ID: {project_id}")

        # 2. テストIssueを作成
        print("\n--- 2. Creating Test Issue ---")
        issue_title = f"Test Issue from GitHubClient ({os.urandom(4).hex()})"
        created_issue = await client.create_issue(
            title=issue_title,
            body="This is a test issue created by the GitHubClient class.",
            labels=["test", "automated"],
        )
        issue_node_id = created_issue.get("node_id")
        issue_number = created_issue.get("number")
        issue_html_url = created_issue.get("html_url")

        if not issue_node_id:
            print("Issueの作成に成功しましたが、Node IDが取得できませんでした。")
            print(f"Created Issue Response: {created_issue}")
            return
        print(f"Test issue created: #{issue_number} (Node ID: {issue_node_id})")
        print(f"Issue URL: {issue_html_url}")

        # 3. Issueをプロジェクトに追加
        print("\n--- 3. Adding Issue to Project ---")
        item_id = await client.add_issue_to_project_v2(project_id, issue_node_id)

        if item_id:
            print(
                f"Issue #{issue_number} successfully added to project {project_number} (Project ID: {project_id})."
            )
            print(f"Project Item ID: {item_id}")
        else:
            print(f"Failed to add issue #{issue_number} to project {project_number}.")

    except httpx.HTTPStatusError as e:
        print(f"\n--- Error ---")
        print(f"An HTTP error occurred: {e}")
        # エラーレスポンスの詳細を表示 (既に _request 内で表示されるが念のため)
        # print(f"Response body: {e.response.text}")
    except Exception as e:
        print(f"\n--- Error ---")
        print(f"An unexpected error occurred: {e}")
        import traceback

        traceback.print_exc()


# if __name__ == "__main__":
#     import asyncio
#     from dotenv import load_dotenv
#     # テスト実行時は .env ファイルを読み込む
#     # load_dotenv() # _main_test 内で実行される
#     # asyncio.run(_main_test())
