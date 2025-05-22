from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class IssueData:
    id: str
    title: str
    description: str
    url: str
    status: str
    created_at: datetime
    updated_at: datetime
    labels: List[str] = field(default_factory=list)
    

class IssuesRepository(ABC):
    
    @abstractmethod
    def fetch_issues(self, project_id: str, *args, **kwargs) -> list[IssueData]:
        """
        指定されたプロジェクトIDに基づいてIssueを取得します。
        
        Args:
            project_id: 取得するIssueのプロジェクトID。
            
        Returns:
            list[IssueData]: 取得したIssueのリスト。
        """
        pass
    
    
    @abstractmethod
    def fetch_projects(self, *args, **kwargs) -> list[dict[str, str]]:
        """
        プロジェクトの一覧を取得します。
        
        Returns:
            list[dict[str, str]]: プロジェクトIDと名前の辞書のリスト。
        """
        pass