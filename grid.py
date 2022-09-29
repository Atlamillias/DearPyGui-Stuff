import types
import dataclasses
from typing import NamedTuple, Generator, Literal, Any
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
    coords2: tuple[int, int] = ()
    width  : int             = 0
    height : int             = 0


@dataclasses.dataclass(slots=True)
class GridSeries:
    """Information regarding a grid's row or column.

    Note that if the cumulative *size* value of all series of an axis exceeds the grid
    target item's available content region, the grid (and its items) can clip beyond it.

    Args:
        * weight (float): The initial weight for the series. Affects the percentage of space
        the series will occupy in comparison to other series' when using the "sized" policy.
        Defaults to 1.0.

        * size (int): The minimum width/height of the column/row. Should not be less
        than 0. Defaults to 0.

        * policy (int): The resizing rule for the series. A value of 0 uses a "sized" policy
        where the series can expand and shrink as the grid is redrawn, but will maintain its
        minimum size. A value of 1 uses a "fixed" policy where the series will not resize with
        the grid. Default is 0.
    """
    SIZED = 0
    FIXED = 1

    weight: float         = 1.0
    size  : int           = 0
    policy: Literal[0, 1] = SIZED




def _resize_axis(arr: list[GridSeries], amount: int) -> None:
    """Args:
        * arr (array[float]): The array containing the series' of a single axis.

        * amount (int): If the number is positive, a new GridSeries object is appended
        to the array. If negative, the array will be trimmed from the end by that many
        values.
    """
    current_length = len(arr)
    if amount >= current_length:
        arr.extend((GridSeries() for _ in range(amount)))
    else:
        del arr[-1: (amount-1): -1]  # trim in-place


def _iter_weights(arr: list[GridSeries]) -> Generator[float, None, None]:
    for gridline in arr:
        yield gridline.weight


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

    __IndexError = IndexError("`index` outside of grid range.")

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
        if rows < 1:
            raise ValueError("Requires at least 1 row.")
        if cols < 1:
            raise ValueError("Requires at least 1 column.")
        self._target  = target
        self._rows    = [GridSeries() for _ in range(rows)]  # y axis
        self._cols    = [GridSeries() for _ in range(cols)]  # x axis
        self._spacing = Point(*spacing)
        self._padding = Point(*padding)

        self._items: dict[ItemId, GridItem] = {}
        self.items = types.MappingProxyType(self._items)

    def __getitem__(self, index):
        return self.get_item(*index)

    def __setitem__(self, index: tuple[int, int], item: int) -> None:
        if not isinstance(index, tuple) and len(index) != 2:
            return NotImplemented
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

    def clear(self) -> None:
        """De-couple all items from the grid. Their current positions will be unchanged,
        but will not be managed further."""
        self._items.clear()

    def clear_item(self, item: ItemId) -> None:
        """De-couple an item from the grid. It's current position will be unchanged,
        but will not be managed further.
        """
        self._items.pop(item, None)

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
            _resize_axis(self._rows, rows - len(self._rows))
        if cols > 0:
            _resize_axis(self._cols, cols - len(self._cols))
        if padding:
            self._padding = Point(*padding)
        if spacing:
            self._spacing = Point(*spacing)
        self.redraw()

    def configure_col(
        self,
        index: int,
        *,
        weight: float         = None,
        policy: Literal[0, 1] = None,
        width : int           = None,
    ) -> None:
        """Updates the configuration of the specified column.

        Args:
            * index (int): Target column index.

            The following are optional keyword-only arguments;

            * weight (float): A weight value for the column. The floor for this value is 0.2.

            * policy (int): The resizing rule for the column. A value of 0 uses a "sized" policy
            where the column will expand and shrink as the grid is redrawn, but will maintain
            a minimum *width*. A value of 1 uses a "fixed" policy where the column will not
            resize with the grid. Default is 0.

            * width (int): The horizontal size of the column. Values below 0 are ignored.
        """
        self._configure_series(self._rows, index, weight=weight, policy=policy, size=width)

    def configure_row(
        self,
        index: int,
        *,
        weight: float         = None,
        policy: Literal[0, 1] = None,
        height: int           = None,
    ) -> None:
        """Updates the configuration of the specified row.

        Args:
            * index (int): Target row index.

            The following are optional keyword-only arguments;

            * weight (float): A weight value for the row. The floor for this value is 0.2.

            * policy (int): The resizing rule for the row. A value of 0 uses a "sized" policy
            where the row will expand and shrink as the grid is redrawn, but will maintain
            a minimum *height*. A value of 1 uses a "fixed" policy where the row will not
            resize with the grid. Default is 0.

            * height (int): The vertical size of the row. Values below 0 are ignored.
        """
        self._configure_series(self._rows, index, weight=weight, policy=policy, size=height)

    def get_col_configuration(self, index: int) -> dict[str, Any]:
        """Return the configuration of a specified column.

        Args:
            * index (int): Target column index.
        """
        return self._get_series_configuration(self._cols, index)

    def get_row_configuration(self, index: int) -> dict[str, Any]:
        """Return the configuration of a specified row.

        Args:
            * index (int): Target row index.
        """
        return self._get_series_configuration(self._rows, index)

    def get_coords(self, item: ItemId) -> tuple[tuple[int, int], tuple[int, int]]:
        """Return the cell range coordinates of an item managed by the grid."""
        griditem = self._items[item]
        coords1  = griditem[1]
        return coords1, griditem[2] or coords1

    def get_item(self, row: int, col: int) -> int | str | None:
        """Return the first item found in the grid at `(<row>, <col>)`, or None if the cell
        is empty.
        """
        for item, (row1, col1), coords2, *_ in self._items.values():
            row2, col2 = coords2 or row1, col1
            if row1 <= row <= row2 and col1 <= col <= col2:
                return item

        # No item at index -- check if the indexes are valid.
        try:
            self._rows[row]
            self._cols[col]
        except IndexError:
            raise IndexError("`row` or `col` outside of grid range.") from None
        return None

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
        c1 = c1 % c_count if c1 != -1 else r1
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
        self._items[item] = GridItem(item, (r1, c1), (r2, c2), max_width, max_height)
        self.redraw()

    def redraw(self, *args, **kwargs) -> None:
        """Force the grid to recalculate the positions and sizes of all managed
        items.

        Ideally, this should be passed as a resize callback for the target item
        or viewport.
        """
        # This might be a good spot to grab DearPyGui's mutex, but that's the
        # application's responsibility and not the grid's.
        cells   = self._get_cells()
        row_cnt = len(self._rows)
        col_cnt = len(self._cols)
        for item, (r1, c1), (r2, c2), item_width, item_height, *_ in self._items.values():
            x_pos , y_pos , width1, height1 = cells[(r1 % row_cnt, c1 % col_cnt)]  # normalizing idxs
            x_offs, y_offs, width2, height2 = cells[(r2 % row_cnt, c2 % col_cnt)]
            # adjust the dimensions for "merged" cells
            cell_width  = x_offs + width2  - x_pos
            cell_height = y_offs + height2 - y_pos
            # sizing item to fit the cell space
            if not item_width or item_width > cell_width:
                item_width = cell_width
            if not item_height or item_height > cell_height:
                item_height = cell_height
            configure_item(
                item,
                pos=(int(x_pos), int(y_pos)),
                width=int(item_width),
                height=int(item_height),
            )

    #### INTERNAL METHODS ####
    def _configure_series(
        self,
        targets: list[GridSeries],
        index  : int,
        *,
        weight : float         = None,
        policy : Literal[0, 1] = None,
        size   : int           = None,
    ) -> None:
        try:
            tgt = targets[index]
        except IndexError:
            raise self.__IndexError from None
        # The arguments are checked pretty hard because the outcome at runtime
        # can be weird and confusing.
        if weight is not None:
            if not weight >= 0.2:  # prevents wonky scaling
                raise ValueError("`weight` cannot be set below 0.2.")
            tgt.weight = weight
        if policy is not None:
            # I consider this error QoL -- FIXED is the only value that's checked
            # against; uses SIZED behavior otherwise.
            if policy not in (GridSeries.FIXED, GridSeries.SIZED):
                raise ValueError("`policy` should be 0 (sized) or 1 (fixed).")
            tgt.policy = policy
        # Don't really need to be noisy here. I'm not sure what a user
        # would expect by passing a negative value anyway.
        if size is not None and size >= 0:
            tgt.size = size
        self.redraw()

    def _get_series_configuration(self, targets: list[GridSeries], index: int) -> dict[str, Any]:
        try:
            return dataclasses.asdict(targets[index])
        except IndexError:
            raise self.__IndexError from None

    def _get_cells(self) -> dict[Point, Rect]:
        """Return the coordinates and bounding boxes of all cells in the grid."""
        # Performance matters here -- localizing as many common vars
        # outside of loops as possible while minimizing function calls.
        FIXED = GridSeries.FIXED
        SIZED = GridSeries.SIZED

        # grid
        rows  = self._rows
        cols  = [*enumerate(self._cols)]  # iterated over several times
        cells = {}

        # content region rect
        _item_cfg = get_item_configuration(self._target)
        cont_x_pos, cont_y_pos = self._padding   # coords are item relative, so always 0 + padding
        cont_width  = (_item_cfg["width" ] - cont_x_pos - cont_x_pos)
        cont_height = (_item_cfg["height"] - cont_y_pos - cont_y_pos)

        # width/height value (in pixels) of 1 weight
        weight_wt_val = cont_width  / sum(_iter_weights(self._cols))
        weight_ht_val = cont_height / sum(_iter_weights(rows))

        # cell rect stuff -- each cell is responsible for half of the total spacing
        x_spacing, y_spacing = self._spacing
        cell_x_pad = x_spacing / 2
        cell_y_pad = y_spacing / 2

        cumulative_height = 0.0
        for row, row_cfg in enumerate(rows):
            row_min_ht = row_cfg.size
            row_height = weight_ht_val * row_cfg.weight
            if row_min_ht > row_height or row_cfg.policy == FIXED \
            or cumulative_height > cont_height:
                row_height = row_min_ht

            # cell rect (vertical)
            cell_y_pos  = cont_y_pos + cumulative_height + cell_y_pad
            cell_height = row_height - y_spacing

            cumulative_width = 0.0
            for col, col_cfg in cols:
                col_min_wt = col_cfg.size
                col_width  = weight_wt_val * col_cfg.weight
                if col_min_wt > col_width or col_cfg.policy == FIXED \
                or cumulative_width > cont_width:
                    col_width = col_min_wt

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
    dpg.create_context()
    dpg.create_viewport(width=720, height=400)
    dpg.setup_dearpygui()
    colors = [(200, 0, 0,), (0, 200, 0), (0, 0, 200), (200, 200, 0), (200, 0, 200)]
    themes = []
    for i in range(5):
        with dpg.theme() as theme:
            with dpg.theme_component(0):
                color = colors[i]
                dpg.add_theme_color(dpg.mvThemeCol_Button, [*color, 50])
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, [*color, 255])
        themes.append(theme)

    with dpg.window(width=400, height=400, no_scrollbar=True, no_background=True) as win:
        btn1 = dpg.add_button(label="RED")
        dpg.bind_item_theme(btn1, themes[0])
        btn2 = dpg.add_button(label="GREEN")
        dpg.bind_item_theme(btn2, themes[1])
        btn3 = dpg.add_button(label="BLUE")
        dpg.bind_item_theme(btn3, themes[2])
        btn4 = dpg.add_button(label=f"YELLOW")
        dpg.bind_item_theme(btn4, themes[3])
        btn5 = dpg.add_button(label=f"PURPLE")
        dpg.bind_item_theme(btn5, themes[4])

        grid = Grid(win, cols=4, rows=4, spacing=(10, 10), padding=(10,10))
        grid.configure_row(1, weight=0.2)
        grid.pack(btn1,  0, 0, -1, 2)
        grid.pack(btn2,  1, 1)
        grid.pack(btn3,  2, 2)
        grid.pack(btn4,  -1, 3)
        grid.pack(btn5,  3, 1, 2, 0)


    def resize_callback():
        grid.redraw()

    dpg.set_primary_window(win, True)
    dpg.set_viewport_resize_callback(resize_callback)
    dpg.show_viewport()
    while dpg.is_dearpygui_running():
        dpg.render_dearpygui_frame()