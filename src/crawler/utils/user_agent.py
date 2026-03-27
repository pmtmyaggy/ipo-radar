"""User-Agent 管理器.

管理HTTP请求的用户代理字符串，符合各数据源的要求。
"""

import os


class UserAgentManager:
    """User-Agent 管理器.
    
    根据数据源要求生成合适的User-Agent字符串。
    SEC EDGAR要求User-Agent必须包含联系邮箱。
    
    Attributes:
        contact_email: 联系邮箱，用于SEC EDGAR等数据源
        app_name: 应用名称
        app_version: 应用版本
    
    Example:
        >>> ua = UserAgentManager(contact_email="user@example.com")
        >>> ua.get_headers()
        {'User-Agent': 'IPO-Radar/0.1.0 (contact: user@example.com)'}
    """

    DEFAULT_APP_NAME = "IPO-Radar"
    DEFAULT_APP_VERSION = "0.1.0"
    DEFAULT_CONTACT_EMAIL = "contact@example.com"

    # 浏览器User-Agent（用于需要模拟浏览器的场景）
    BROWSER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    ]

    def __init__(
        self,
        contact_email: str | None = None,
        app_name: str | None = None,
        app_version: str | None = None,
    ):
        """初始化User-Agent管理器.
        
        Args:
            contact_email: 联系邮箱，优先从环境变量 EDGAR_USER_AGENT 读取
            app_name: 应用名称
            app_version: 应用版本
        """
        # 从环境变量或参数获取联系邮箱。
        #
        # 某些数据源（例如 Nasdaq 浏览器模式）并不要求邮箱，但整个项目里很多
        # crawler 会在初始化阶段统一创建 UserAgentManager。这里如果硬性抛错，
        # 会让大量与 EDGAR 无关的功能在构造时直接失败。
        env_ua = os.getenv("EDGAR_USER_AGENT", "")
        env_email = os.getenv("CONTACT_EMAIL", "")
        env_identity = os.getenv("EDGAR_IDENTITY", "")
        self._using_fallback_contact = False

        if env_identity and "@" in env_identity:
            self.contact_email = env_identity
        elif env_ua and "@" in env_ua:
            self.contact_email = env_ua.split()[-1] if "@" in env_ua.split()[-1] else env_ua
        elif env_email and "@" in env_email:
            self.contact_email = env_email
        elif contact_email and "@" in contact_email:
            self.contact_email = contact_email
        else:
            self.contact_email = self.DEFAULT_CONTACT_EMAIL
            self._using_fallback_contact = True

        self.app_name = app_name or self.DEFAULT_APP_NAME
        self.app_version = app_version or self.DEFAULT_APP_VERSION

    def get_standard(self) -> str:
        """获取标准User-Agent.
        
        格式: AppName/Version (contact: email)
        
        Returns:
            标准User-Agent字符串
        """
        return f"{self.app_name}/{self.app_version} (contact: {self.contact_email})"

    def get_edgar(self) -> str:
        """获取SEC EDGAR专用User-Agent.
        
        SEC要求User-Agent必须包含联系邮箱，格式：
        Sample Company Name AdminContact@<sample company domain>.com
        
        Returns:
            符合SEC要求的User-Agent
        """
        return f"{self.app_name} {self.contact_email}"

    def get_browser(self, index: int | None = None) -> str:
        """获取浏览器User-Agent.
        
        用于需要模拟浏览器的场景，如某些网站会检查User-Agent。
        
        Args:
            index: 浏览器User-Agent的索引，None则随机选择
        
        Returns:
            浏览器User-Agent字符串
        """
        if index is not None and 0 <= index < len(self.BROWSER_AGENTS):
            return self.BROWSER_AGENTS[index]

        import random
        return random.choice(self.BROWSER_AGENTS)

    def get_headers(
        self,
        user_agent_type: str = "standard",
        extra_headers: dict | None = None,
    ) -> dict:
        """获取完整的请求头.
        
        Args:
            user_agent_type: User-Agent类型
                - "standard": 标准格式
                - "edgar": SEC EDGAR专用
                - "browser": 浏览器格式
            extra_headers: 额外的请求头
        
        Returns:
            请求头字典
        """
        # 选择User-Agent
        if user_agent_type == "edgar":
            ua = self.get_edgar()
        elif user_agent_type == "browser":
            ua = self.get_browser()
        else:
            ua = self.get_standard()

        # 基础请求头
        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

        # 浏览器类型添加更多头
        if user_agent_type == "browser":
            headers.update({
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            })

        # 合并额外请求头
        if extra_headers:
            headers.update(extra_headers)

        return headers

    def validate_email(self, email: str) -> bool:
        """验证邮箱格式.
        
        Args:
            email: 邮箱地址
        
        Returns:
            是否有效
        """
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def check_configuration(self) -> dict:
        """检查配置是否有效.
        
        Returns:
            配置状态字典
        """
        return {
            "contact_email_set": not self._using_fallback_contact,
            "contact_email_valid": self.validate_email(self.contact_email) if self.contact_email else False,
            "using_fallback_contact_email": self._using_fallback_contact,
            "app_name": self.app_name,
            "app_version": self.app_version,
            "standard_ua": self.get_standard(),
            "edgar_ua": self.get_edgar(),
        }


# 便捷函数
def get_default_headers(extra: dict | None = None) -> dict:
    """获取默认请求头.
    
    Args:
        extra: 额外请求头
    
    Returns:
        请求头字典
    """
    manager = UserAgentManager()
    return manager.get_headers(extra_headers=extra)


def get_edgar_headers() -> dict:
    """获取SEC EDGAR专用请求头.
    
    Returns:
        符合SEC要求的请求头
    """
    manager = UserAgentManager()
    return manager.get_headers(user_agent_type="edgar")
