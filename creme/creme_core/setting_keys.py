from django.utils.translation import gettext_lazy as _

# from . import constants
from .core.setting_key import SettingKey

global_filters_edition_key = SettingKey(
    id='creme_core-global_filters_edition',
    description=_(
        'Filters & views of list without owner can be edited by all users? '
        '("No" means only superusers are allowed to)'
    ),
    app_label='creme_core', type=SettingKey.BOOL,
)
block_opening_key = SettingKey(  # TODO: rename with "brick"
    # id=constants.SETTING_BRICK_DEFAULT_STATE_IS_OPEN,
    id='creme_core-default_block_state_is_open',  # TODO: rename with "brick"
    description=_('By default, are blocks open?'),
    app_label='creme_core', type=SettingKey.BOOL,
)
block_showempty_key = SettingKey(  # TODO: rename with "brick"
    # id=constants.SETTING_BRICK_DEFAULT_STATE_SHOW_EMPTY_FIELDS,
    id='creme_core-default_block_state_show_empty_fields',  # TODO: rename with "brick"
    description=_('By default, are empty fields displayed?'),
    app_label='creme_core', type=SettingKey.BOOL,
)
currency_symbol_key = SettingKey(
    # id=constants.DISPLAY_CURRENCY_LOCAL_SYMBOL,
    id='creme_core-display_currency_local_symbol',
    description=_(
        'Display the currency local symbol (e.g. €)? '
        'If no the international symbol will be used (ex: EUR)'
    ),
    app_label='creme_core', type=SettingKey.BOOL,
)
