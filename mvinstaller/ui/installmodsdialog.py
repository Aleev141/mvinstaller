from typing import Optional
from flet import (
    UserControl, Dropdown, dropdown, Text, AlertDialog, TextButton, Column, Row, TextField, Container, Checkbox, IconButton, icons
)
from mvinstaller.addon_metadata import get_metadata, metadata_text
from mvinstaller.config import get_config
from mvinstaller.localetools import get_locale_name
from mvinstaller.multiverse import get_mv_mainmods, get_addons
from mvinstaller.localetools import localize as _
from mvinstaller.ui.busycontainer import BusyContainer
from mvinstaller.ui.errorsnackbar import ErrorSnackbar
from mvinstaller.ui.infoscheme import InfoSchemeType

class InstallModsDialog(UserControl):
    def __init__(self, error_snackbar: Optional[ErrorSnackbar]=None, on_install=None):
        self._locale_picker = None
        self._busycontainer = None
        self._dlg = None
        self._error_snackbar = error_snackbar
        self._on_install = on_install
        super().__init__()

    def _set_mod_description(self, id):
        def on_change(e):
            self._mod_description.value = metadata_text(get_metadata(id))
            self._mod_description.update()
        return on_change
    
    def _get_matching_addons(self, locale):
        locale = locale.replace('.machine', '')
        addons = [
                addon
                for addon in get_addons()
                if len(addon.compatible_mv_locale) == 0 or (locale in addon.compatible_mv_locale)
            ]
        addon_names = [addon.modname for addon in addons]
        valid_addons = []
        for addon in addons:
            if len(addon.dependent_modnames) == 0:
                valid_addons.append(addon)
                continue
            for dependent in addon.dependent_modnames:
                if not dependent in addon_names:
                    break
            else:
                valid_addons.append(addon)
        return valid_addons

    def _update_addon_list(self):
        locale = self._locale_picker.value
        if locale:
            matching_addons = self._get_matching_addons(locale)
            max_page = (len(matching_addons) -1) // 7
            self._addon_index.data = 0
            self._addon_index.value = f'1/{max_page + 1}'
            self._addon_index.update()
            self._addon_list.controls = [
                Checkbox(
                    label=get_metadata(addon.id).title,
                    on_change=self._set_mod_description(addon.id),
                    data=addon.id,
                    visible = True if i // 7 == 0 else False
                )
                for i, addon in enumerate(matching_addons)
            ]
        else:
            self._addon_list.controls = []
        
        self._addon_list.update()
    
    def _turn_addon_list(self, diff: int):
        dist = self._addon_index.data + diff
        if dist < 0:
            return
        locale = self._locale_picker.value
        if not locale:
            return
        matching_addons = self._get_matching_addons(locale)
        max_page = (len(matching_addons) -1) // 7
        if max_page < dist:
            return
        self._addon_index.data = dist
        self._addon_index.value = f'{dist + 1}/{max_page + 1}'
        self._addon_index.update()
        checked_addon_id_list = [addon.data for addon in self._addon_list.controls if addon.value == True]
        self._addon_list.controls = [
            Checkbox(
                label=get_metadata(addon.id).title,
                on_change=self._set_mod_description(addon.id),
                data=addon.id,
                visible = True if i // 7 == dist else False,
                value = True if addon.id in checked_addon_id_list else False
            )
            for i, addon in enumerate(matching_addons)
        ]
        self._addon_list.update()
    
    def _build_content(self):
        self._busycontainer.busy = True
        self.update()

        try:
            mainmods = get_mv_mainmods()
            if len(mainmods) == 0:
                raise RuntimeError('Failed to fetch the list of main mods')
        except Exception as e:
            if self._error_snackbar:
                self._error_snackbar.message(InfoSchemeType.Error, str(e))
            self._close(False)
            return

        mainmod_locales = [mainmod.locale for mainmod in mainmods]
        self._locale_picker.options = [
            dropdown.Option(
                mainmod.locale,
                f'{mainmod.version} {get_locale_name(mainmod.locale)}'
            )
            for mainmod in mainmods
        ]
        if self._locale_picker.value not in mainmod_locales:
            app_locale = get_config().app_locale
            self._locale_picker.value = app_locale if app_locale in mainmod_locales else mainmod_locales[0]

        self._update_addon_list()

        self._busycontainer.busy = False
        self.update()

    def build(self):
        def locale_picker_on_change(e):
            self._update_addon_list()
            try:
                mainmods = get_mv_mainmods()
                mainmod = next(mod for mod in mainmods if mod.locale == self._locale_picker.value)
                self._set_mod_description(mainmod.id)(e)
            except StopIteration:
                pass
        
        self._locale_picker = Dropdown(
            options=[],
            on_change=lambda e: locale_picker_on_change(e)
        )
        self._addon_index = Text()
        self._addon_list = Column()
        self._mod_description = TextField(
            read_only=True,
            multiline=True,
            min_lines=20,
            max_lines=20,
            text_size=12,
            expand=True
        )
        self._busycontainer = BusyContainer(
            Container(
                Row(
                    [
                        Column(
                            [
                                Text(_('install-mods-language')),
                                self._locale_picker,
                                Row(
                                    [
                                        Text(_('install-mods-addons')),
                                        IconButton(icons.CHEVRON_LEFT, on_click=lambda e: self._turn_addon_list(-1)),
                                        self._addon_index,
                                        IconButton(icons.CHEVRON_RIGHT, on_click=lambda e: self._turn_addon_list(1))
                                    ]
                                ),
                                self._addon_list
                            ],
                            horizontal_alignment='start'
                        ),
                        self._mod_description
                    ],
                    tight=True,
                    vertical_alignment='start',
                ),
                width=800
            )
        )
        self._dlg = AlertDialog(
            modal=True,
            title=Text(_('install-mods-dialog-title')),
            content=self._busycontainer,
            actions=[
                TextButton(content=Text(_('install-mods-dialog-action-install')), on_click=lambda e: self._close(True)),
                TextButton(content=Text(_('cancel')), on_click=lambda e: self._close(False))
            ]
        )
        return self._dlg
    
    def open(self):
        self._dlg.open = True
        self._build_content()
    
    def _close(self, install):
        self._dlg.open = False
        self.update()
        if install and self._on_install:
            locale = self._locale_picker.value
            selected_addons = [
                checkbox.data
                for checkbox in self._addon_list.controls
                if checkbox.value == True
            ]
            print(locale, selected_addons)
            self._on_install(locale, selected_addons)
