import asyncio
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Union,
)

from anyio import create_task_group


EventsMapping = Union[Dict[str, Union["Callable[..., Any]", "EventHandler"]], "Events"]


def event(
    function: Optional[Callable[..., Any]] = None,
    stop_propagation: bool = False,
    prevent_default: bool = False,
) -> Union["EventHandler", Callable[[Callable[..., Any]], "EventHandler"]]:
    """Create an event handler function with extra functionality.

    While you're always free to add callbacks by assigning them to an element's attributes

    .. code-block:: python

        element = idom.html.button({"onClick": my_callback})

    You may want the ability to prevent the default action associated with the event
    from taking place, or stoping the event from propagating up the DOM. This decorator
    allows you to add that functionality to your callbacks.

    Parameters:
        function:
            A callback responsible for handling the event.
        stop_propagation:
            Block the event from propagating further up the DOM.
        prevent_default:
            Stops the default actional associate with the event from taking place.
    """
    handler = EventHandler(stop_propagation, prevent_default)
    if function is not None:
        handler.add(function)
        return handler
    else:
        return handler.add


class Events(Mapping[str, "EventHandler"]):
    """A container for event handlers.

    Assign this object to the ``"eventHandlers"`` field of an element model.
    """

    __slots__ = "_handlers"

    def __init__(self) -> None:
        self._handlers: Dict[str, EventHandler] = {}

    def on(
        self, event: str, stop_propagation: bool = False, prevent_default: bool = False
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """A decorator for adding an event handler.

        Parameters:
            event:
                The camel-case name of the event, the word "on" is automatically
                prepended. So passing "keyDown" would refer to the event "onKeyDown".
            stop_propagation:
                Block the event from propagating further up the DOM.
            prevent_default:
                Stops the default actional associate with the event from taking place.

        Returns:
            A decorator which accepts an event handler function as its first argument.
            The parameters of the event handler function may indicate event attributes
            which should be sent back from the frontend. See :class:`EventHandler` for
            more info.

        Examples:
            Simple "onClick" event handler:

            .. code-block:: python

                def clickable_element():
                    events = Events()

                    @events.on("click")
                    def handler(event):
                        # do something on a click event
                        ...

                    return idom.vdom("button", "hello!", eventHandlers=events)
        """
        if not event.startswith("on"):
            event = "on" + event[:1].upper() + event[1:]

        if event not in self._handlers:
            handler = EventHandler(stop_propagation, prevent_default)
            self._handlers[event] = handler
        else:
            handler = self._handlers[event]

        def setup(function: Callable[..., Any]) -> Callable[..., Any]:
            handler.add(function)
            return function

        return setup

    def __contains__(self, key: Any) -> bool:
        return key in self._handlers

    def __len__(self) -> int:
        return len(self._handlers)

    def __iter__(self) -> Iterator[str]:
        return iter(self._handlers)

    def __getitem__(self, key: str) -> "EventHandler":
        return self._handlers[key]

    def __repr__(self) -> str:  # pragma: no cover
        return repr(self._handlers)


class EventHandler:
    """An object which defines an event handler.

    The event handler object acts like a coroutine when called.

    Parameters:
        event_name:
            The camel case name of the event.
        target_id:
            A unique identifier for the event handler. This is generally used if
            an element has more than on event handler for the same event type. If
            no ID is provided one will be generated automatically.
    """

    __slots__ = (
        "__weakref__",
        "_coro_handlers",
        "_func_handlers",
        "prevent_default",
        "stop_propagation",
    )

    def __init__(
        self,
        stop_propagation: bool = False,
        prevent_default: bool = False,
    ) -> None:
        self.stop_propagation = stop_propagation
        self.prevent_default = prevent_default
        self._coro_handlers: List[Callable[..., Coroutine[Any, Any, Any]]] = []
        self._func_handlers: List[Callable[..., Any]] = []

    def add(self, function: Callable[..., Any]) -> "EventHandler":
        """Add a callback to the event handler.

        Parameters:
            function:
                The event handler function. Its parameters may indicate event attributes
                which should be sent back from the fronend unless otherwise specified by
                the ``properties`` parameter.
        """
        if asyncio.iscoroutinefunction(function):
            self._coro_handlers.append(function)
        else:
            self._func_handlers.append(function)
        return self

    def remove(self, function: Callable[..., Any]) -> None:
        """Remove the function from the event handler.

        Raises:
            ValueError: if not found
        """
        if asyncio.iscoroutinefunction(function):
            self._coro_handlers.remove(function)
        else:
            self._func_handlers.remove(function)

    async def __call__(self, data: List[Any]) -> Any:
        """Trigger all callbacks in the event handler."""
        if self._coro_handlers:
            async with create_task_group() as group:
                for handler in self._coro_handlers:
                    await group.spawn(handler, *data)
        for handler in self._func_handlers:
            handler(*data)

    def __contains__(self, function: Any) -> bool:
        if asyncio.iscoroutinefunction(function):
            return function in self._coro_handlers
        else:
            return function in self._func_handlers
