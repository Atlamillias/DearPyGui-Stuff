import types
import dataclasses
import enum
from typing import NamedTuple, Generator, Any
from dearpygui import dearpygui as dpg
from dearpygui._dearpygui import (
    get_item_configuration,
    configure_item,
)

__all__ = [
    "Point",
    "Rect",
    "Grid",
]


ItemId = int | str


class Point(NamedTuple):
    x: float
    y: float


class Rect(NamedTuple):
    x     : float
    y     : float
    width : float
    height: float


class GridItem(NamedTuple):
    """Information regarding an item managed by a Grid object.

    Args:
        * item (int | str): Identifier of a DearPyGui item.

        * coords1 (tuple[float, float]): Starting coordinates of the cell used to place the
        item.

        * coords2 (tuple[float, float]): End coordinates of the cell used to place the item.
        A non-default value indicates the item is filling multiple series'. Defaults to ().

        * width (int): If the item's column uses a "sized" policy, then this value is
        treated as the item's maximum width and will not be expanded beyond it. However, it
        can still shrink down to the column's width constraint when necessary. The default
        value of 0 means the item will always scale horizontally to the size of the available
        content region. Defaults to 0.

        * height (int): If the item's row uses a "sized" policy, then this value is treated
        as the item's maximum height and will not be expanded beyond it. However, it can
        still shrink down to the row's height constraint when necessary. The default value
        of 0 means the item will always scale vertically to the size of the available content
        region. Defaults to 0.
    """

    item   : ItemId
    coords1: tuple[int, int]
    coords2: tuple[int, int]
    width  : int             = 0
    height : int             = 0
    anchor : str             = ""


@dataclasses.dataclass(slots=True)
class GridSeries:
    """Information regarding a grid's row or column."""
    _WEIGHT  = 1.0
    _MINSIZE = 0

    weight: float = _WEIGHT
    size  : int   = _MINSIZE

    def configure(self, *, weight: float = None, size: int = None, **kwargs) -> None:
        if weight is not None:
            self.weight = max(0, weight)
        if size is not None:
            self.size = max(0, size)

    def configuration(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class GridAxis:
    __slots__ = ("_axis",)

    _WEIGHT  = GridSeries._WEIGHT
    _MINSIZE = GridSeries._MINSIZE

    def __init__(self, length: int):
        self._axis: list[GridSeries] = []
        self.resize(length)  # populate list

    def __getitem__(self, index: int) -> GridSeries:
        return self._axis[index]

    def __iter__(self) -> Generator[GridSeries, None, None]:
        yield from self._axis

    def __len__(self) -> int:
        return self._axis.__len__()

    def resize(self, amount: int) -> None:
        """Args:
            * amount (int): If the number is positive, a new GridSeries object is appended
            to the array based on the value. If negative, the array will be trimmed from the
            end by that many values.
        """
        arr = self._axis
        if amount >= len(arr):
            arr.extend((GridSeries() for _ in range(amount)))
        else:
            del arr[-1: (amount-1): -1]  # trim in-place

    def get_weight(self) -> float:
        return sum(s.weight for s in self._axis if not s.size)

    def get_min_size(self) -> int:
        return sum(s.size for s in self._axis)


class Grid:
    """A layout manager for DearPyGui. Aligns items in a virtual table-like structure.

    Rows and columns are zero-indexed.


    Properties
        * target [get]
        * items [get]
        * rows [get, set]
        * cols [get, set]
        * spacing [get, set]
        * padding [get, set]
    """

    __slots__ = (
        "items",
        "_items",
        "_target",
        "_spacing",
        "_padding",
        "_rows",
        "_cols",
    )

    def __init__(self, target: ItemId, *, cols: int = 1, rows: int = 1, spacing: Point = (0, 0), padding: Point = (0, 0)):
        """Args:
            * target (int | str): The item to scale the grid to. It must have a valid rect (i.e.
            position, width, height).

            * cols (int, optional): The number of columns in the grid. Cannot be set below 1.
            Defaults to 1.

            * rows (int, optional): The number of rows in the grid. Cannot be set below 1. Defaults
            to 1.

            * spacing (Point, optional): The horizontal and vertical space between cells. Defaults
            to (0, 0).

            * padding (Point, optional): The horizontal and vertical space between the target item's
            bounding box and an outer cell. Defaults to (0, 0).
        """
        if rows < 1 or cols < 1:
            raise ValueError("Minimum 1 column and 1 row.")
        self._target  = target
        self._spacing = Point(*spacing)
        self._padding = Point(*padding)
        # These are the representation of each axis and their series/slots; accessible
        # through their actual index.
        self._rows = GridAxis(rows)
        self._cols = GridAxis(cols)

        self._items: dict[ItemId, GridItem] = {}
        self.items = types.MappingProxyType(self._items)

    def __setitem__(self, index: tuple[int, int], item: int) -> None:
        self.pack(item, *index)

    @property
    def target(self) -> ItemId:
        """[get]: The item that the grid scales to."""
        return self._target

    @property
    def rows(self) -> int:
        """[get, set]: The number of rows in the grid. Cannot be set below 1.
        """
        return len(self._rows)
    @rows.setter
    def rows(self, value: int) -> None:
        self.configure_grid(rows=value)

    @property
    def cols(self) -> int:
        """[get, set]: The number of columns in the grid. Cannot be set below 1.
        """
        return len(self._cols)
    @cols.setter
    def cols(self, value: int) -> None:
        self.configure_grid(cols=value)

    @property
    def spacing(self) -> Point:
        """[get, set]: The horizontal and vertical space between cells."""
        return self._spacing
    @spacing.setter
    def spacing(self, value: tuple[int, int]) -> None:
        self.configure_grid(spacing=value)

    @property
    def padding(self) -> Point:
        """[get, set]: The horizontal and vertical space between the target item's
        bounding box and an outer cell.
        """
        return self._padding
    @padding.setter
    def padding(self, value: tuple[int, int]) -> None:
        self.configure_grid(padding=value)

    def configure_grid(
        self,
        *,
        rows       : int                         = 0,
        cols       : int                         = 0,
        padding    : tuple[int, int]             = (),
        spacing    : tuple[int, int]             = (),
    ) -> None:
        """Update the grid's settings.

        Args:
            * rows (int, optional): The number of rows in the grid. A value below 1
            is ignored.

            * cols (int, optional): The number of rows in the grid. A value below 1
            is ignored.

            * padding (tuple[int, int], optional): The horizontal and vertical space between
            cells.

            * spacing (tuple[int, int], optional): The horizontal and vertical space between
            the target item's bounding box and an outer cell.
        """
        # TODO: Get noisy when a user tries to trim the grid while items
        # occupy the space.
        if rows > 0:
            self._rows.resize(rows - len(self._rows))
        if cols > 0:
            self._cols.resize(cols - len(self._cols))
        if padding:
            self._padding = Point(*padding)
        if spacing:
            self._spacing = Point(*spacing)
        # self.redraw()?

    def configure_col(
        self,
        index: int,
        *,
        weight: float = None,
        width : int   = None,
    ) -> None:
        """Updates the configuration of the specified column.

        Args:
            * index (int): Target column index.

            The following are optional keyword-only arguments;

            * weight (float): The weight value for the column. Extra horizontal space in the
            grid is distributed among columns proportional to their weight values IF the column
            does not have a set *height*. A value less than 0 is treated as 0.

            * width (int): The width of the column. A value less than 0 is treated as
            0.
        """
        self._cols[index].configure(weight=weight, size=width)
        # self.redraw()?

    def configure_row(
        self,
        index: int,
        *,
        weight: float = None,
        height: int   = None,
    ) -> None:
        """Updates the configuration of the specified row.

        Args:
            * index (int): Target row index.

            The following are optional keyword-only arguments;

            * weight (float): The weight value for the row. Extra vertical space in the
            grid is distributed among rows proportional to their weight values IF the row
            does not have a set *height*. A value less than 0 is treated as 0.

            * height (int): The minimum height of the row. A value less than 0 is treated
            as 0.
        """
        self._rows[index].configure(weight=weight, size=height)
        # self.redraw()?

    def get_col_configuration(self, index: int):
        """Return the configuration of a specified column.

        Args:
            * index (int): Target column index.
        """
        return self._cols[index].configuration()

    def get_row_configuration(self, index: int):
        """Return the configuration of a specified row.

        Args:
            * index (int): Target row index.
        """
        return self._rows[index].configuration()

    def pack(
        self,
        item: int,
        r1  : int,
        c1  : int,
        r2  : int = None,
        c2  : int = None,
        *,
        max_width : int = 0,
        max_height: int = 0,
        anchor    : str = "nw",
    ):
        """Add an item to be manged by the grid and position it in a cell. It's size will
        be adjusted to fit the cell's content region.

        Args:
            * item (int): Identifier for an item. It must have a valid rect (i.e.
            position, width, height).

            * r1 (int): The target row index. The indexing behavior is identical to
            indexing a Python sequence.

            * c1 (int): The target column index. The indexing behavior is identical
            to indexing a Python sequence.

            * r2 (int): If provided, the item will occupy a range of rows from *r1* to
            and including *r2*. The indexing behavior is identical to indexing a Python
            sequence. Defaults to None.

            * c2 (int): If provided, the item will occupy a range of columns from *c1*
            to and including *c2*. The indexing behavior is identical to indexing a Python
            sequence. Defaults to None.

            The following optional keyword-only arguments.

            * max_width (int): If the item's column uses a "sized" policy, then this value is
            treated as the item's maximum width and will not be expanded beyond it. However, it
            will still shrink down to the column's width constraint when necessary. A value of 0
            means the item will always scale horizontally to the size of the available content
            region. A value less than 0 is treated as 0. Defaults to 0.

            * max_height (int): If the item's row uses a "sized" policy, then this value is treated
            as the item's maximum height and will not be expanded beyond it. However, it will
            still shrink down to the row's height constraint when necessary. A value of 0 means
            the item will always scale vertically to the size of the available content region. A
            value less than 0 is treated as 0. Defaults to 0.

            * anchor (str): Affects the item's alignment and/or justification in the cell(s).
            Accepted values are 'n', 'ne', 'e', 'se', 's', 'sw', 'w', 'nw', and 'c'. Not case-
            sensitive. Defaults to 'nw'.
        """
        rows = self._rows
        cols = self._cols
        # validate indexes
        try:
            rows[r1]
            rows[c1]
            cols[r2 or 0]
            cols[c2 or 0]
        except IndexError:
            raise IndexError("Index(s) outside of grid range.") from None
        # Normalizing indexes. -1 needs to be preserved for redraws so the item
        # will always be positioned at the last series of the axis, even if the
        # number of series changes.
        r_count = len(rows)
        c_count = len(cols)
        r1 = r1 % r_count if r1 != -1 else r1
        c1 = c1 % c_count if c1 != -1 else c1
        if r2 is not None:
            r2 = r2 % r_count if r2 != -1 else r2
        else:
            r2 = r1
        if c2 is not None:
            c2 = c2 % c_count if c2 != -1 else c2
        else:
            c2 = c1
        # Correct a backwards anchor or negative range.
        if r1 > r2 and r2 != -1:
            r1, r2 = r2, r1
        if c1 > c2 and c2 != -1:
            c1, c2 = c2, c1

        max_width  = 0 if max_width  < 0 else max_width
        max_height = 0 if max_height < 0 else max_height

        try:
            anchor = anchor.lower() if anchor else "nw"
        except TypeError:
            raise TypeError(f"`anchor` should be a string (got {type(anchor)}).")
        if anchor not in self.ANCHORS:
            raise ValueError(f"Accepted `anchor` values; 'n', 'ne', 'e', 'se', 's', 'sw', 'w', 'nw', 'c' (got {anchor!r}).")

        self._items[item] = GridItem(item, (r1, c1), (r2, c2), max_width, max_height, anchor)
        self.redraw()

    def redraw(self, *args, **kwargs) -> None:
        """Force the grid to recalculate the positions and sizes of all managed
        items.

        Ideally, this should be passed as a resize callback for the target item
        or viewport.
        """
        # This would be a good spot to lock DearPyGui's mutex but that's the application's
        # responsibility, not the grid's.
        ANCHORS = self.ANCHORS
        cells   = self._get_cells()
        row_cnt = len(self._rows)
        col_cnt = len(self._cols)
        for item, (r1, c1), (r2, c2), item_width, item_height, anchor, *_ in self._items.values():
            x_pos , y_pos , width1, height1 = cells[(r1 % row_cnt, c1 % col_cnt)]  # normalizing idxs
            x_offs, y_offs, width2, height2 = cells[(r2 % row_cnt, c2 % col_cnt)]  # normalizing idxs
            # Adjust the dimensions for "merged" cells.
            cell_width  = x_offs + width2  - x_pos
            cell_height = y_offs + height2 - y_pos
            # Sizing item to fit the cell space.
            if not item_width or item_width > cell_width:
                item_width = cell_width
            if not item_height or item_height > cell_height:
                item_height = cell_height
            configure_item(
                item,
                # anchor funcs don't do much unless the item is smaller than the cell
                pos=ANCHORS[anchor](item_width, item_height, x_pos, y_pos, cell_width, cell_height),
                # Due to how DPG interprets size values, the width/height cannot be
                # lower than 1 as it would actually make the item larger...
                width=max(int(item_width), 1),
                height=max(int(item_height), 1),
            )

    ANCHORS = {
        "n" : lambda i_wt, i_ht, c_x, c_y, c_wt, c_ht: (int((c_wt - i_wt) / 2 + c_x), int(                    c_y)),  # center x
        "ne": lambda i_wt, i_ht, c_x, c_y, c_wt, c_ht: (int((c_wt - i_wt)     + c_x), int(                    c_y)),
        "e" : lambda i_wt, i_ht, c_x, c_y, c_wt, c_ht: (int((c_wt - i_wt)     + c_x), int((c_ht - i_ht) / 2 + c_y)),  # center y
        "se": lambda i_wt, i_ht, c_x, c_y, c_wt, c_ht: (int((c_wt - i_wt)     + c_x), int((c_ht - i_ht)     + c_y)),
        "s" : lambda i_wt, i_ht, c_x, c_y, c_wt, c_ht: (int((c_wt - i_wt) / 2 + c_x), int((c_ht - i_ht)     + c_y)),  # center x
        "sw": lambda i_wt, i_ht, c_x, c_y, c_wt, c_ht: (int(                    c_x), int((c_ht - i_ht)     + c_y)),
        "w" : lambda i_wt, i_ht, c_x, c_y, c_wt, c_ht: (int(                    c_x), int((c_ht - i_ht) / 2 + c_y)),  # center y
        "nw": lambda i_wt, i_ht, c_x, c_y, c_wt, c_ht: (int(                    c_x), int(                    c_y)),
        "c" : lambda i_wt, i_ht, c_x, c_y, c_wt, c_ht: (int((c_wt - i_wt) / 2 + c_x), int((c_ht - i_ht) / 2 + c_y)),  # center x & y
    }

    #### INTERNAL/PRIVATE ####

    def _get_cells(self) -> dict[Point, Rect]:
        """Return the coordinates and bounding boxes of all cells in the grid."""
        # Performance matters here -- localizing as many common vars
        # outside of loops as possible while minimizing function calls.

        # content region #
        _item_cfg = get_item_configuration(self._target)
        cont_x_pos, cont_y_pos = self._padding   # item relative coords -- always 0 + padding
        cont_width  = (_item_cfg["width" ] - cont_x_pos - cont_x_pos)
        cont_height = (_item_cfg["height"] - cont_y_pos - cont_y_pos)

        # This will be distributed between rows/columns proportional to their
        # individial weight values.
        unalloc_width  = max(0, cont_width  - self._cols.get_min_size())
        unalloc_height = max(0, cont_height - self._rows.get_min_size())
        # The pixel value each "weight" is worth from the remaining space.
        width_per_weight  = unalloc_width  / (self._cols.get_weight() or 1)  # ZeroDivisionError
        height_per_weight = unalloc_height / (self._rows.get_weight() or 1)  # ZeroDivisionError

        # cell rect stuff -- each cell is responsible for half of the spacing
        x_spacing, y_spacing = self._spacing
        cell_x_pad = x_spacing / 2
        cell_y_pad = y_spacing / 2

        rows = self._rows
        cols = [*enumerate(self._cols)]

        cells = {}
        cumulative_height = 0.0
        for row, row_cfg in enumerate(rows):
            # A series with a set size value will not auto-size with the grid.
            row_height = row_cfg.size or height_per_weight * row_cfg.weight
            # cell rect (vertical)
            cell_y_pos  = cont_y_pos + cumulative_height + cell_y_pad
            cell_height = row_height - y_spacing

            cumulative_width = 0.0
            for col, col_cfg in cols:
                # A series with a set size value will not auto-size with the grid.
                col_width = col_cfg.size or width_per_weight * col_cfg.weight
                # cell rect (horizontal)
                cell_x_pos = cont_x_pos + cumulative_width + cell_x_pad
                cell_width = col_width - x_spacing

                cumulative_width += col_width

                cells[(row, col)] = Rect(
                    cell_x_pos,
                    cell_y_pos,
                    cell_width,
                    cell_height,
                )

            cumulative_height += row_height
        return cells


if __name__ == '__main__':
    from random import randint


    def bind_button_theme():
        while True:
            item = yield
            rgb  = randint(0, 255), randint(0, 255), randint(0, 255)
            with dpg.theme() as theme:
                with dpg.theme_component(0):
                    dpg.add_theme_color(dpg.mvThemeCol_Button, [*rgb, 80])
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, [*rgb, 255])
            dpg.bind_item_theme(item, theme)

    def create_button():
        themes = bind_button_theme().send
        themes(None)
        while True:
            tag = dpg.generate_uuid()
            item = dpg.add_button(label=tag, tag=tag)
            themes(item)
            yield item


    create_button = create_button().__next__  # ye olde' button factory


    dpg.create_context()
    dpg.create_viewport(title="Grid Demo", width=600, height=600, min_height=10, min_width=10)
    dpg.setup_dearpygui()


    with dpg.window(no_scrollbar=True, no_background=True) as win:
        grid = Grid(win, cols=6, rows=6, padding=(5, 5), spacing=(5, 5))

        # Without additional arguments, items will expand and shrink to the cell's size.
        grid.pack(create_button(),  0,  2)  # first row
        grid.pack(create_button(), -1,  3)  # last row

        # You can clamp an item's width/height and include an alignment option. Valid
        # options are 'n', 'ne', 'e', 'se', 's', 'sw', 'w', 'nw', and 'c'.
        grid.pack(create_button(), 1, 1, max_height=25, anchor="w")  # west (centered)
        grid.pack(create_button(), 1, 1, max_width=25, anchor="n")   # north (centered)
        grid.pack(create_button(), 4, 4, max_height=25, anchor="w")

        # These items will occupy a range of cells.
        grid.pack(create_button(),  3,  1,  4,  2)
        grid.pack(create_button(),  1,  3,  2,  4)
        grid.pack(create_button(),  4,  0, -1,  1)
        grid.pack(create_button(),  0,  4,  1, -1)

        for anchor in grid.ANCHORS:  # '
            kwargs = dict(max_width=50, max_height=50, anchor=anchor)
            # pack to individual cells (cont.)
            grid.pack(create_button(),  0,  0, **kwargs)  # first row & column
            grid.pack(create_button(), -1, -1, **kwargs)  # last row & column
            # pack to a "merged cell" (cont.)
            grid.pack(create_button(),  2,  2,  3,  3, **kwargs)

        # You can change the weight or set a fixed size for a row/column.
        grid.configure_col(2, weight=0.5)  # |
        grid.configure_col(3, weight=0.5)  # |-- These middle rows and columns will scale
        grid.configure_row(2, weight=0.5)  # |-- to half the size of other rows/columns.
        grid.configure_row(3, weight=0.5)  # |

    dpg.set_primary_window(win, True)
    dpg.show_viewport()
    # Be sure to add the grid's redraw method to a callback. Otherwise it won't resize!
    dpg.set_viewport_resize_callback(grid.redraw)


    while dpg.is_dearpygui_running():
        dpg.render_dearpygui_frame()