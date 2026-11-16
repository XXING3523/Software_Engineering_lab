"""领域层异常。"""


class DomainError(Exception):
    """所有可预期的业务错误的基类。"""


class ValidationError(DomainError):
    """输入数据不满足领域约束。"""


class InvalidTransitionError(DomainError):
    """状态转换不被状态机允许。"""


class CapacityError(DomainError):
    """名额或容量操作不合法。"""


class PermissionDeniedError(DomainError):
    """当前用户没有执行操作所需的角色。"""


class DuplicateRequestError(DomainError):
    """请求编号已经被另一个结果占用。"""


class NotFoundError(DomainError):
    """请求的业务对象不存在。"""


class ConflictError(DomainError):
    """业务对象版本或并发条件发生冲突。"""
