from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import TYPE_CHECKING, Callable, Optional, Union

if TYPE_CHECKING:
    import matplotlib.axes
    import matplotlib.colorbar

from qcodes.dataset.data_set_protocol import DataSetProtocol
from qcodes.dataset.measurements import Measurement
from qcodes.dataset.plotting import plot_and_save_image
from qcodes.parameters import MultiParameter, ParameterBase

if TYPE_CHECKING:
    from qcodes.dataset.descriptions.versioning.rundescribertypes import Shapes

log = logging.getLogger(__name__)

ActionsT = Sequence[Callable[[], None]]
BreakConditionT = Callable[[], bool]

ParamMeasT = Union[ParameterBase, Callable[[], None]]

AxesTuple = tuple["matplotlib.axes.Axes", "matplotlib.colorbar.Colorbar"]
AxesTupleList = tuple[
    list["matplotlib.axes.Axes"], list[Optional["matplotlib.colorbar.Colorbar"]]
]
AxesTupleListWithDataSet = tuple[
    DataSetProtocol,
    tuple[Optional["matplotlib.axes.Axes"], ...],
    tuple[Optional["matplotlib.colorbar.Colorbar"], ...],
]
MultiAxesTupleListWithDataSet = tuple[
    tuple[DataSetProtocol, ...],
    tuple[tuple["matplotlib.axes.Axes", ...], ...],
    tuple[tuple[Optional["matplotlib.colorbar.Colorbar"], ...], ...],
]


class BreakConditionInterrupt(Exception):
    pass


MeasInterruptT = Union[KeyboardInterrupt, BreakConditionInterrupt, None]


def _register_parameters(
    meas: Measurement,
    param_meas: Sequence[ParamMeasT],
    setpoints: Sequence[ParameterBase] | None = None,
    shapes: Shapes | None = None,
) -> None:
    real_parameters = [
        param for param in param_meas if isinstance(param, ParameterBase)
    ]

    for parameter in real_parameters:
        meas.register_parameter(parameter, setpoints=setpoints)

    if shapes is not None:
        parameter_names = [param.full_name for param in real_parameters]
        for param in real_parameters:
            if isinstance(param, MultiParameter):
                parameter_names.extend(param.full_names)

        filtered_shapes = {
            name: shape for name, shape in shapes.items() if name in parameter_names
        }
        meas.set_shapes(shapes=filtered_shapes)


def _set_write_period(meas: Measurement, write_period: float | None = None) -> None:
    if write_period is not None:
        meas.write_period = write_period


def _handle_plotting(
    data: DataSetProtocol,
    do_plot: bool = True,
    interrupted: MeasInterruptT = None,
) -> AxesTupleListWithDataSet:
    """
    Save the plots created by datasaver as pdf and png

    Args:
        data: a dataset to generate plots from
            as plot.
        do_plot: Should a plot be produced

    """
    res: AxesTupleListWithDataSet
    if do_plot:
        res = plot_and_save_image(data)
    else:
        res = data, (None,), (None,)

    if interrupted:
        log.warning(
            f"Measurement has been interrupted, data may be incomplete: {interrupted}"
        )

    return res


def _register_actions(
    meas: Measurement, enter_actions: ActionsT, exit_actions: ActionsT
) -> None:
    for action in enter_actions:
        # this omits the possibility of passing
        # argument to enter and exit actions.
        # Do we want that?
        meas.add_before_run(action, ())
    for action in exit_actions:
        meas.add_after_run(action, ())


@contextmanager
def _catch_interrupts() -> Iterator[Callable[[], MeasInterruptT]]:
    interrupt_exception = None

    def get_interrupt_exception() -> MeasInterruptT:
        nonlocal interrupt_exception
        return interrupt_exception

    try:
        yield get_interrupt_exception
    except (KeyboardInterrupt, BreakConditionInterrupt) as e:
        interrupt_exception = e
