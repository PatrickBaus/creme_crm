################################################################################
#    Creme is a free/open-source Customer Relationship Management software
#    Copyright (C) 2024 Hybird
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
################################################################################

from __future__ import annotations

from django.db.transaction import atomic
from django.utils.translation import gettext as _

from creme.creme_core.core.exceptions import ConflictError
from creme.creme_core.models import CremeEntity, CremeUser

from . import copying


class EntityCloner:
    """This class manages the cloning of CremeEntities.
     - is a user allowed to clone?
     - perform the cloning.

    Hint: see class <EntityClonerRegistry>.
    """
    pre_save_copiers: list[type[copying.Copier]] = [
        copying.RegularFieldsCopier,
    ]
    post_save_copiers: list[type[copying.Copier]] = [
        copying.ManyToManyFieldsCopier,
        copying.CustomFieldsCopier,
        copying.PropertiesCopier,
        copying.RelationsCopier,
    ]

    def check_permissions(self, *, user: CremeUser, entity: CremeEntity) -> None:
        """Checks if the given instance can be cloned.
        If an exception is raised, the cloning is forbidden (the exception
        should contain the reason -- a translated human readable one).
        @raise PermissionDenied, ConflictError.
        """
        if entity.is_deleted:
            raise ConflictError(_('A deleted entity cannot be cloned'))

        user.has_perm_to_create_or_die(entity)
        user.has_perm_to_view_or_die(entity)

    def _build_instance(self, *, user, source) -> CremeEntity:
        return type(source)()

    def _pre_save(self, *, user, source, target) -> None:
        for copier_class in self.pre_save_copiers:
            copier_class(source=source, user=user).copy_to(target=target)

    def _post_save(self, *, user, source, target) -> None:
        for copier_class in self.post_save_copiers:
            copier_class(source=source, user=user).copy_to(target=target)

    @atomic
    def perform(self, *, user: CremeUser, entity: CremeEntity) -> CremeEntity:
        """Performs the cloning.

        @param user: the logged user (could be used by some custom cloner
               classes to make some check).
        @param entity: Instance to clone.
        """
        clone = self._build_instance(user=user, source=entity)

        self._pre_save(user=user, source=entity, target=clone)
        clone.save()
        self._post_save(user=user, source=entity, target=clone)

        return clone


class EntityClonerRegistry:
    """Stores the cloning behaviours per CremeEntity model."""
    class RegistrationError(Exception):
        pass

    class UnRegistrationError(RegistrationError):
        pass

    def __init__(self):
        self._cloner_classes: dict[type[CremeEntity], type[EntityCloner]] = {}

    # TODO: 'def clone(instance):' ?

    def get(self, model: type[CremeEntity]) -> EntityCloner | None:
        """Hint: if None is returned, you should not clone the instances of
        the given model.
        """
        cls = self._cloner_classes.get(model)

        return None if cls is None else cls()

    def register(self,
                 model: type[CremeEntity],
                 cloner_class=EntityCloner,
                 ) -> EntityClonerRegistry:
        """Hint: register a child class of EntityCloner if you want to
        customise the cloning behaviour.
        """
        if self._cloner_classes.setdefault(model, cloner_class) is not cloner_class:
            raise self.RegistrationError(f'<{model.__name__}> has already a cloner')

        return self

    def unregister(self, model: type[CremeEntity]) -> EntityClonerRegistry:
        try:
            del self._cloner_classes[model]
        except KeyError as e:
            raise self.UnRegistrationError(
                f'<{model.__name__}> has no cloner (not registered or already unregistered)'
            ) from e

        return self


entity_cloner_registry = EntityClonerRegistry()
