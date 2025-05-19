import requests
from datetime import datetime
from repositories.issues.issues_repository import IssuesRepository, IssueData
from typing import Any, List, Dict, Optional


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
    
    def __fetch_repository_issues(self, owner: str, name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        特定のリポジトリからIssueを取得します。
        
        Args:
            owner: リポジトリのオーナー名。
            name: リポジトリ名。
            limit: 取得するIssueの最大数。
            
        Returns:
            List[Dict[str, Any]]: 取得したIssueのリスト。
        """
        query = """
            query getRepositoryIssues($owner: String!, $name: String!, $first: Int) {
                repository(owner: $owner, name: $name) {
                    issues(first: $first) {
                        nodes {
                            id
                            title
                            body
                            state
                            url
                            createdAt
                            updatedAt
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
        """
        variables = {
            "owner": owner,
            "name": name,
            "first": limit,
        }
        result = self.__run_query(query, variables)
        
        try:
            issues = result["data"]["repository"]["issues"]["nodes"]
            return issues
        except (KeyError, TypeError):
            # リポジトリやIssueが見つからない場合は空のリストを返す
            return []
    
    def fetch_issues(self, project_id: str, *args, **kwargs) -> List[IssueData]:
        """
        指定されたプロジェクトIDに基づいてIssueを取得します。
        プロジェクト内の全リポジトリからIssueを収集します。
        
        Args:
            project_id: 取得するIssueのプロジェクトID。
            
        Returns:
            List[IssueData]: 取得したIssueのリスト。
        """
        # プロジェクト内のリポジトリを取得
        repositories = self.__get_project_repositories(project_id)
        
        # 全リポジトリからIssueを収集
        all_issues = []
        for repo in repositories:
            issues = self.__fetch_repository_issues(repo["owner"], repo["name"])
            
            # 辞書形式のIssueをIssueDataオブジェクトに変換
            for issue in issues:
                issue_data = IssueData(
                    id=issue["id"],
                    title=issue["title"],
                    description=issue["body"],
                    url=issue["url"],
                    status=issue["state"],
                    created_at=datetime.fromisoformat(issue.get("createdAt", datetime.now().isoformat()).replace('Z', '+00:00')),
                    updated_at=datetime.fromisoformat(issue.get("updatedAt", datetime.now().isoformat()).replace('Z', '+00:00'))
                )
                all_issues.append(issue_data)
        
        return all_issues
        
