import requests
from datetime import datetime
from repositories.issues.issues_repository import IssuesRepository, IssueData
from typing import Any, List, Dict, Optional, cast


class GitHubIssuesRepository(IssuesRepository):
    
    def __init__(self, token: str):
        self.__token = token
        self.__api_url = "https://api.github.com/graphql"
        self.__headers = {
            "Authorization": f"Bearer {self.__token}",
            "Accept": "application/vnd.github+json",
        }
    
    def __run_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        GraphQLクエリを実行します。
        
        Args:
            query: 実行するGraphQLクエリ。
            variables: クエリに渡す変数。
            
        Returns:
            Dict[str, Any]: クエリの結果。
            
        Raises:
            Exception: クエリの実行に失敗した場合。
        """
        response = requests.post(
            self.__api_url,
            headers=self.__headers,
            json={"query": query, "variables": variables},
        )
        response.raise_for_status()
        data = response.json()
        if "errors" in data:
            raise Exception(data["errors"][0]["message"])
        return data
    
    def __get_project_repositories(self, project_id: str) -> List[Dict[str, str]]:
        """
        プロジェクトに関連するリポジトリを取得します。
        
        Args:
            project_id: プロジェクトID。
            
        Returns:
            List[Dict[str, str]]: リポジトリ情報のリスト。各リポジトリは「owner」と「name」のキーを持ちます。
        """
        # プロジェクト内のアイテム（IssueやPR）を取得
        query = """
            query GetProjectItems($projectId: ID!) {
                node(id: $projectId) {
                    ... on ProjectV2 {
                        items(first: 100) {
                            nodes {
                                id
                                content {
                                    __typename
                                    ... on Issue {
                                        repository {
                                            name
                                            owner {
                                                login
                                            }
                                        }
                                    }
                                    ... on PullRequest {
                                        repository {
                                            name
                                            owner {
                                                login
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        """
        variables = {"projectId": project_id}
        result = self.__run_query(query, variables)
        
        repositories = []
        unique_repos = set()  # 重複を避けるためのセット
        
        items = result.get("data", {}).get("node", {}).get("items", {}).get("nodes", [])
        
        # IssueやPRからリポジトリ情報を抽出
        for item in items:
            content = item.get("content", {})
            if not content:
                continue
                
            typename = content.get("__typename")
            if typename in ["Issue", "PullRequest"]:
                repo = content.get("repository")
                if repo:
                    owner = repo.get("owner", {}).get("login")
                    name = repo.get("name")
                    
                    if owner and name:
                        # 重複チェック
                        repo_key = f"{owner}/{name}"
                        if repo_key not in unique_repos:
                            unique_repos.add(repo_key)
                            repositories.append({
                                "owner": owner,
                                "name": name
                            })
        
        return repositories
    
    def __fetch_repository_issues(self, owner: str, name: str, state: Optional[str] = None, 
                           labels: Optional[List[str]] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        特定のリポジトリからIssueを取得します。
        
        Args:
            owner: リポジトリのオーナー名。
            name: リポジトリ名。
            state: Issueの状態でフィルタリング（'OPEN'、'CLOSED'、None=全て）。
            labels: フィルタリングするラベルのリスト。
            limit: 取得するIssueの最大数。
            
        Returns:
            List[Dict[str, Any]]: 取得したIssueのリスト。
        """
        # GraphQLのフィルタ引数を構築
        filter_args = "first: $first"
        if state:
            filter_args += ", states: [$state]"
        
        # ラベルフィルタの追加
        labels_filter = ""
        if labels and len(labels) > 0:
            labels_filter = ", labels: $labels"
            filter_args += labels_filter
        
        query = f"""
            query getRepositoryIssues($owner: String!, $name: String!, $first: Int{', $state: IssueState' if state else ''}{', $labels: [String!]' if labels and len(labels) > 0 else ''}) {{
                repository(owner: $owner, name: $name) {{
                    issues({filter_args}) {{
                        nodes {{
                            id
                            title
                            body
                            state
                            url
                            createdAt
                            updatedAt
                            labels(first: 10) {{
                                nodes {{
                                    name
                                    color
                                }}
                            }}
                            repository {{
                                name
                                owner {{
                                    login
                                }}
                            }}
                            projectItems(first: 1) {{
                                nodes {{
                                    project {{
                                        id
                                        title
                                    }}
                                    fieldValues(first: 8) {{
                                        nodes {{
                                            __typename
                                            ... on ProjectV2ItemFieldSingleSelectValue {{
                                                name
                                            }}
                                        }}
                                    }}
                                }}
                            }}
                        }}
                        pageInfo {{
                            hasNextPage
                            endCursor
                        }}
                        totalCount
                    }}
                }}
            }}
        """
        
        variables = {
            "owner": owner,
            "name": name,
            "first": limit,
        }
        
        if state:
            variables["state"] = state
        
        if labels and len(labels) > 0:
            variables["labels"] = labels
        
        result = self.__run_query(query, variables)
        
        try:
            issues = result["data"]["repository"]["issues"]["nodes"]
            return issues
        except (KeyError, TypeError) as e:
            # エラーログを出力
            print(f"Error fetching issues for {owner}/{name}: {str(e)}")
            # リポジトリやIssueが見つからない場合は空のリストを返す
            return []
    
    def fetch_issues(self, project_id: str, *args, **kwargs) -> List[IssueData]:
        """
        指定されたプロジェクトIDに基づいてIssueを取得します。
        プロジェクト内の全リポジトリからIssueを収集します。
        
        Args:
            project_id: 取得するIssueのプロジェクトID。
            state: (オプション) Issueの状態でフィルタリング（'OPEN'、'CLOSED'、None=全て）。
            labels: (オプション) フィルタリングするラベルのリスト。
            limit_per_repo: (オプション) リポジトリごとに取得するIssueの最大数。デフォルトは100。
            
        Returns:
            List[IssueData]: 取得したIssueのリスト。
        
        Examples:
            >>> repository = GitHubIssuesRepository(token)
            >>> # すべてのIssueを取得
            >>> all_issues = repository.fetch_issues(project_id)
            >>> # オープン状態のIssueのみ取得
            >>> open_issues = repository.fetch_issues(project_id, state='OPEN')
            >>> # 特定のラベルを持つIssueを取得
            >>> bug_issues = repository.fetch_issues(project_id, labels=['bug'])
            >>> # 複数の条件でフィルタリング
            >>> filtered_issues = repository.fetch_issues(project_id, state='OPEN', labels=['enhancement'], limit_per_repo=50)
        """
        # オプションパラメータの取得
        state = kwargs.get('state')
        labels = kwargs.get('labels')
        limit_per_repo = kwargs.get('limit_per_repo', 100)
        
        # プロジェクト内のリポジトリを取得
        repositories = self.__get_project_repositories(project_id)
        
        if not repositories:
            print(f"No repositories found for project ID: {project_id}")
            return []
        
        # 全リポジトリからIssueを収集
        all_issues = []
        for repo in repositories:
            try:
                issues = self.__fetch_repository_issues(
                    owner=repo["owner"], 
                    name=repo["name"],
                    state=state,
                    labels=labels,
                    limit=limit_per_repo
                )
                
                # 辞書形式のIssueをIssueDataオブジェクトに変換
                for issue in issues:
                    # ラベル情報の抽出
                    issue_labels = []
                    if issue.get("labels") and issue["labels"].get("nodes"):
                        issue_labels = [label["name"] for label in issue["labels"]["nodes"]]
                    
                    # プロジェクトステータス情報の抽出
                    project_status = None
                    if issue.get("projectItems") and issue["projectItems"].get("nodes"):
                        project_items = issue["projectItems"]["nodes"]
                        for project_item in project_items:
                            if project_item.get("fieldValues") and project_item["fieldValues"].get("nodes"):
                                for field_value in project_item["fieldValues"]["nodes"]:
                                    # ProjectV2ItemFieldSingleSelectValue を使用
                                    if field_value and "name" in field_value and field_value.get("__typename") == "ProjectV2ItemFieldSingleSelectValue":
                                        project_status = field_value["name"]
                                        break
                    
                    issue_data = IssueData(
                        id=issue["id"],
                        title=issue["title"],
                        description=issue["body"] or "",  # Noneの場合は空文字列に
                        url=issue["url"],
                        status=issue["state"],
                        created_at=datetime.fromisoformat(issue.get("createdAt", datetime.now().isoformat()).replace('Z', '+00:00')),
                        updated_at=datetime.fromisoformat(issue.get("updatedAt", datetime.now().isoformat()).replace('Z', '+00:00')),
                        labels=issue_labels,
                        project_status=project_status
                    )
                    all_issues.append(issue_data)
            except Exception as e:
                print(f"Error fetching issues from {repo['owner']}/{repo['name']}: {str(e)}")
                continue
        
        return all_issues
    
    def fetch_projects(self, *args, **kwargs) -> List[Dict[str, str]]:
        """
        ユーザーのプロジェクト一覧を取得します。
        
        Returns:
            List[Dict[str, str]]: プロジェクトIDと名前の辞書のリスト。
            各辞書は「id」と「name」のキーを持ちます。
        """
        query = """
            query {
                viewer {
                    projectsV2(first: 100) {
                        nodes {
                            id
                            title
                            number
                            closed
                        }
                    }
                }
            }
        """
        
        result = self.__run_query(query)
        
        projects = []
        try:
            project_nodes = result.get("data", {}).get("viewer", {}).get("projectsV2", {}).get("nodes", [])
            
            for project in project_nodes:
                # 閉じられていないプロジェクトのみを含める
                if not project.get("closed", False):
                    projects.append({
                        "id": project["id"],
                        "name": project["title"]
                    })
                    
            return projects
        except (KeyError, TypeError):
            # プロジェクトが見つからない場合は空のリストを返す
            return []
            
    def update_issue(self, issue_id: str, title: Optional[str] = None, description: Optional[str] = None, status: Optional[str] = None, project_status: Optional[str] = None) -> Optional[IssueData]:
        """
        GitHubのIssueを更新します。
        
        Args:
            issue_id: 更新するIssueのID
            title: 新しいタイトル（指定しない場合は変更なし）
            description: 新しい説明（指定しない場合は変更なし）
            status: 新しいステータス（'OPEN'または'CLOSED'、指定しない場合は変更なし）
            project_status: 新しいプロジェクトステータス（指定しない場合は変更なし）
        
        Returns:
            Optional[IssueData]: 更新されたIssueのデータ。更新に失敗した場合はNone。
        """
        # 更新するフィールドを準備
        update_fields = []
        variables = {"issueId": issue_id}
        issue_data = None
        updated_project_status = None
        
        # プロジェクトステータスのみが提供された場合は、まずIssueデータを取得する必要がある
        if title is None and description is None and status is None and project_status is not None:
            query = """
                query GetIssue($issueId: ID!) {
                    node(id: $issueId) {
                        ... on Issue {
                            id
                            title
                            body
                            state
                            url
                            createdAt
                            updatedAt
                            labels(first: 10) {
                                nodes {
                                    name
                                }
                            }
                        }
                    }
                }
            """
            result = self.__run_query(query, variables)
            if result.get("data") and result["data"].get("node"):
                issue_data = result["data"]["node"]
        
        if title is not None:
            update_fields.append("title: $title")
            variables["title"] = title
            
        if description is not None:
            update_fields.append("body: $body")
            variables["body"] = description
            
        if status is not None:
            # ステータスはOPENまたはCLOSEDのみ受け付ける
            if status.upper() not in ["OPEN", "CLOSED"]:
                raise ValueError(f"Invalid status: {status}. Status must be 'OPEN' or 'CLOSED'.")
                
            # GitHubのIssueはOPENまたはCLOSEDのみなので、statusに応じてmutationを選択
            if status.upper() == "CLOSED":
                query = """
                    mutation CloseIssue($issueId: ID!) {
                        closeIssue(input: {issueId: $issueId}) {
                            issue {
                                id
                                title
                                body
                                state
                                url
                                createdAt
                                updatedAt
                                labels(first: 10) {
                                    nodes {
                                        name
                                    }
                                }
                            }
                        }
                    }
                """
                result = self.__run_query(query, variables)
                issue_data = result.get("data", {}).get("closeIssue", {}).get("issue")
            else:  # OPEN
                query = """
                    mutation ReopenIssue($issueId: ID!) {
                        reopenIssue(input: {issueId: $issueId}) {
                            issue {
                                id
                                title
                                body
                                state
                                url
                                createdAt
                                updatedAt
                                labels(first: 10) {
                                    nodes {
                                        name
                                    }
                                }
                            }
                        }
                    }
                """
                result = self.__run_query(query, variables)
                issue_data = result.get("data", {}).get("reopenIssue", {}).get("issue")
        
        # タイトルまたは説明の更新が必要な場合
        if title is not None or description is not None:
            update_mutation = ", ".join(update_fields)
            query = f"""
                mutation UpdateIssue($issueId: ID!{', $title: String' if title is not None else ''}{', $body: String' if description is not None else ''}) {{
                    updateIssue(input: {{id: $issueId, {update_mutation}}}) {{
                        issue {{
                            id
                            title
                            body
                            state
                            url
                            createdAt
                            updatedAt
                            labels(first: 10) {{
                                nodes {{
                                    name
                                }}
                            }}
                        }}
                    }}
                }}
            """
            result = self.__run_query(query, variables)
            issue_data = result.get("data", {}).get("updateIssue", {}).get("issue")
            
        # 更新されたIssueデータがない場合
        if not issue_data:
            return None
            
        # プロジェクトステータスを更新する場合
        if project_status is not None:
            # 1. まずIssueのプロジェクトアイテムIDを取得
            query = """
                query GetProjectItemId($issueId: ID!) {
                    node(id: $issueId) {
                        ... on Issue {
                            projectItems(first: 1) {
                                nodes {
                                    id
                                    project {
                                        id
                                        number
                                    }
                                    fieldValues(first: 20) {
                                        nodes {
                                            ... on ProjectV2ItemFieldSingleSelectValue {
                                                name
                                                field {
                                                    ... on ProjectV2SingleSelectField {
                                                        id
                                                        name
                                                        options {
                                                            id
                                                            name
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            """
            result = self.__run_query(query, {"issueId": issue_id})
            
            project_item_id = None
            status_field_id = None
            option_id = None
            project_items = []
            
            if result.get("data") and result["data"].get("node") and result["data"]["node"].get("projectItems"):
                project_items = result["data"]["node"]["projectItems"].get("nodes", [])
                if project_items and len(project_items) > 0 and project_items[0] is not None:
                    project_item_id = project_items[0].get("id")
                    
                    # ステータスフィールドとオプションを見つける
                    field_values = project_items[0].get("fieldValues", {}).get("nodes", [])
                    for field_value in field_values:
                        if field_value and field_value.get("field") and field_value["field"].get("name") and "status" in field_value["field"]["name"].lower():
                            status_field_id = field_value["field"].get("id")
                            options = field_value["field"].get("options", [])
                            for option in options:
                                if option and option.get("name") and option["name"].lower() == project_status.lower():
                                    option_id = option.get("id")
                                    break
                            break
            
            # 2. プロジェクトアイテムのステータスを更新
            if project_item_id and status_field_id and option_id:
                update_query = """
                    mutation UpdateProjectV2ItemFieldValue($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
                        updateProjectV2ItemFieldValue(
                            input: {
                                projectId: $projectId,
                                itemId: $itemId,
                                fieldId: $fieldId,
                                value: { singleSelectOptionId: $optionId }
                            }
                        ) {
                            projectV2Item {
                                id
                            }
                        }
                    }
                """
                project_id = None
                if project_items and len(project_items) > 0 and project_items[0] is not None and project_items[0].get("project") is not None:
                    project_id = project_items[0]["project"].get("id")
                
                if project_id:
                    update_result = self.__run_query(update_query, {
                        "projectId": project_id,
                        "itemId": project_item_id,
                        "fieldId": status_field_id,
                        "optionId": option_id
                    })
                    
                    if update_result and update_result.get("data") and update_result["data"].get("updateProjectV2ItemFieldValue"):
                        updated_project_status = project_status
    
        # ラベル情報の抽出
        issue_labels = []
        if issue_data.get("labels") and issue_data["labels"].get("nodes"):
            issue_labels = [label["name"] for label in issue_data["labels"]["nodes"]]
            
        # IssueDataオブジェクトに変換して返す
        return IssueData(
            id=issue_data["id"],
            title=issue_data["title"],
            description=issue_data["body"] or "",
            url=issue_data["url"],
            status=issue_data["state"],
            created_at=datetime.fromisoformat(issue_data.get("createdAt", datetime.now().isoformat()).replace('Z', '+00:00')),
            updated_at=datetime.fromisoformat(issue_data.get("updatedAt", datetime.now().isoformat()).replace('Z', '+00:00')),
            labels=issue_labels,
            project_status=updated_project_status
        )
