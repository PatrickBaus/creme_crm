################################################################################
#    Creme is a free/open-source Customer Relationship Management software
#    Copyright (C) 2017-2022  Hybird
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

from django.utils.translation import gettext as _


class PagerLink:
    CHOOSE: str = 'choose'
    PREVIOUS: str = 'previous'
    NEXT: str = 'next'

    page: int | None
    group: str | None
    enabled: bool
    is_current: bool

    def __init__(self,
                 page: int | None,
                 label=None,
                 help=None,
                 group: str = None,
                 enabled: bool = True,
                 is_current: bool = False):
        self.page = page
        self.group = group
        self.enabled = enabled
        self.label = label or str(page)
        self.is_current = is_current

        if help is None:
            self.help = _('To page {}').format(page) if page else ''
        else:
            self.help = help

    @property
    def css(self) -> str:
        css = ['pager-link']

        if not self.enabled or self.is_current:
            css.append('is-disabled')

        if self.group:
            css.append(f'pager-link-{self.group}')

        if self.is_current:
            css.append('pager-link-current')

        return ' '.join(css)

    @property
    def is_choose(self) -> bool:
        return self.group == self.CHOOSE

    def __str__(self):
        return (
            f'PagerLink('
            f'label={self.label}, help={self.help}, group={self.group}, '
            f'enabled={self.enabled}, page={self.page}'
            f')'
        )


class PagerContext:
    count: int
    current: int
    previous: int | None
    next: int | None
    first: int
    last: int

    def __init__(self, page):
        self.page = page

        self.count = page.paginator.num_pages
        self.current = page.number
        self.previous = page.previous_page_number() if page.has_previous() else None
        self.next = page.next_page_number() if page.has_next() else None
        self.first = 1
        self.last = self.count

        self._links = None

    @property
    def links(self) -> list[PagerLink]:
        links = self._links

        if links is None:
            links = self._links = self._build_links()

        return links

    def is_current(self, index: int) -> bool:
        return self.current == index

    def _build_links(self) -> list[PagerLink]:
        page_count = self.count
        page_current = self.current
        page_next = self.next
        page_previous = self.previous
        is_current = self.is_current

        if page_count < 1:
            return []

        # We want to dynamically display links to the most interesting places in the dataset:
        # - around the current page: the previous and next pages
        # - to the beginning and end pages
        # - to an arbitrary page to choose from when there are gaps between the above, but only if
        #   these gaps are big enough: we don't need to display a page chooser if there's a single
        #   page in the gap
        #
        # We'll also unconditionally display text links to the previous and next pages, and disable
        # them when they are not usable.

        links = [
            PagerLink(
                page_previous, label=_('Previous page'),
                group=PagerLink.PREVIOUS,
                enabled=page_previous is not None,
            ),
        ]

        # So the shape we have for the numerical page links is:
        #
        #    first ... previous current next ... last
        #          ^^^                       ^^^
        #          low overflow area         high overflow area
        #
        # The overflow areas model the gaps between the surrounding signposts, and can be empty,
        # show a single page, or a page chooser. Overflow starts to happen above 3 pages. We now
        # handle these 7 parts.

        # 1. We'll always show the first page, whether it's the current, previous, or last pages
        # (for a single page), or we want it displayed because there are enough pages. If there's a
        # single page, we don't use the "first" or "last" labels.
        first_page_help = None if page_count == 1 else _('To first page')
        links.append(PagerLink(1, help=first_page_help, is_current=is_current(1)))

        # 2. The low overflow is the space between the first page excluded, and the previous page
        # excluded. The amount of overflow will decide whether we'll display a page chooser or
        # regular page link.
        lo_overflow = page_current - 3
        if lo_overflow == 1:
            assert page_previous == 3
            # By definition, a singular low overflow can only point to page 2: there's a single
            # page between the first and the previous page 3.
            links.append(PagerLink(2))
        elif lo_overflow >= 2:
            assert page_previous >= 4
            # We have at least 2 pages to choose from, so we display a page chooser.
            links.append(
                PagerLink(page_previous - 1, help=_('To another page'), group=PagerLink.CHOOSE)
            )

        # 3. The link to the previous page is shown when the current page is not the first page
        # (there are no prior pages), and when the previous page itself is not the first (the
        # "first page" handling code above will take care of that).
        if page_current >= 3:
            links.append(
                PagerLink(page_previous)
            )

        # 4. The link to the current page is shown when the current page is not the first or last
        # page (their respective handling code will take care of that).
        if page_current > 1 and page_current < page_count:
            links.append(
                PagerLink(page_current, is_current=True)
            )

        # 5. The link to the next page is shown when the current page is not the last page (there
        # are no later pages), and when the next page itself is not the last (the "last page"
        # handling code below will take care of that).
        if page_current <= page_count - 2:
            links.append(
                PagerLink(page_next)
            )

        # 6. The high overflow is the space between the next page excluded, and the last page
        # excluded. The amount of overflow will decide whether we'll display a page chooser or
        # regular page link.
        hi_overflow = page_count - page_current - 2
        if hi_overflow == 1:
            assert page_next is not None
            # By definition, a singular high overflow can only point to the page following the
            # next: there's a single page between it and the last page.
            links.append(PagerLink(page_next + 1))
        elif hi_overflow >= 2:
            assert page_next is not None
            # We have at least 2 pages to choose from, so we display a page chooser.
            links.append(
                PagerLink(page_next + 1, help=_('To another page'), group=PagerLink.CHOOSE)
            )

        # 7. Unless we only have a single page (in which case the "first page" handling code above
        # took care of that), we always show the last page, whether it's the current or next pages,
        # or we want it displayed because there are enough pages.
        if page_count > 1:
            links.append(
                PagerLink(page_count, help=_('To last page'), is_current=is_current(page_count))
            )

        links.append(
            PagerLink(
                page_next, label=_('Next page'),
                group=PagerLink.NEXT,
                enabled=page_next is not None,
            )
        )

        return links
