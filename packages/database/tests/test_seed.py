from database.models import Permission, Role, RolePermission
from database.seed import PermissionCode, RoleName, seed
from sqlalchemy import func, select


async def _seed(session):
    # seed() is sync + Core; run it on the same transactional connection the
    # async session is bound to, so the rows are visible here and rolled back
    # at teardown like every other test.
    await session.run_sync(lambda sync_session: seed(sync_session.connection()))


async def _role_id(session, name: str) -> int:
    return await session.scalar(select(Role.id).where(Role.name == name))


async def _perm_id(session, code: str) -> int:
    return await session.scalar(select(Permission.id).where(Permission.code == code))


async def test_seed_inserts_roles(session):
    await _seed(session)
    names = set(await session.scalars(select(Role.name)))
    assert names == set(RoleName)


async def test_seed_inserts_permissions(session):
    await _seed(session)
    codes = set(await session.scalars(select(Permission.code)))
    assert codes == set(PermissionCode)


async def test_seed_grants_membership_create_to_instructor_only(session):
    await _seed(session)

    instructor_id = await _role_id(session, RoleName.INSTRUCTOR)
    perm_id = await _perm_id(session, PermissionCode.MEMBERSHIPS_CREATE)

    holders = set(
        await session.scalars(
            select(RolePermission.role_id).where(
                RolePermission.permission_id == perm_id
            )
        )
    )
    assert holders == {instructor_id}


async def test_seed_is_idempotent(session):
    await _seed(session)
    await _seed(session)

    assert await session.scalar(select(func.count()).select_from(Role)) == 3
    assert await session.scalar(select(func.count()).select_from(Permission)) == 1
    assert await session.scalar(select(func.count()).select_from(RolePermission)) == 1
