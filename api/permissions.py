from rest_framework.permissions import BasePermission 


class RolePermission(BasePermission):
    allowed_roles=[]

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and 
            hasattr(request.user,'profile') and 
            request.user.profile.role is not None and 
            request.user.profile.role.name in self.allowed_roles

        )
    
class IsAdminUser(RolePermission):
    allowed_roles=['superadmin']

class IsManagerUser(RolePermission):
    allowed_roles=['general_manager','operations_manager','department_head','sales_manager']

class IsUser(RolePermission):
    allowed_roles=['underwriter','telecallers','customers','accounts']