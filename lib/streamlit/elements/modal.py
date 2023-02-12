# Copyright (c) Streamlit Inc. (2018-2022) Snowflake Inc. (2022)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import TYPE_CHECKING, Optional, cast

from typing_extensions import Literal

from streamlit.elements import form
from streamlit.errors import StreamlitAPIException
from streamlit.proto import Block_pb2
from streamlit.runtime.app_session import create_update_open_modal_id_modal_event
from streamlit.runtime.metrics_util import gather_metrics
from streamlit.runtime.scriptrunner import ScriptRunContext, get_script_run_ctx

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


class ModalMixin:
    @gather_metrics("experimental_modal_form")
    def experimental_modal_form(self, key: str, clear_on_submit: bool = False):
        """Create a modal form that batches elements together with a "Submit" button.

        A modal is a container that groups other elements and widgets together,
        in a way similar to the form, but these elements ale displayed in a modal
         instead of the main container, similiary as form it contains a Submit button.
         When the modal's Submit button is pressed, all widget values inside the modal will be
        sent to Streamlit in a batch.

        To add elements to a modal object, you can use "with" notation
        (preferred) or just call methods directly on the form. See
        examples below.

        Forms have a few constraints:

        * Every modal must contain a ``st.modal_submit_button``.
        * Modal can appear anywhere in your app (sidebar, columns, etc),
          but they cannot be embedded inside other modals or forms.

        Parameters
        ----------
        key : str
            A string that identifies the modal. Each modal must have its own
            key. (This key is not displayed to the user in the interface.)
        clear_on_submit : bool
            If True, all widgets inside the modal will be reset to their default
            values after the user presses the Submit button. Defaults to False.
            (Note that Custom Components are unaffected by this flag, and
            will not be reset to their defaults on modal submission.)

        Examples
        --------
        Inserting elements using "with" notation:

        >>> import streamlit as st
        >>>
        >>> modal_form = st.experimental_modal_form("my_modal")
        >>>
        >>> def cta_callback():
        ...     st.write(f"Hey {st.session_state.first_name} {st.session_state.last_name}!")
        ...     st.write(f"Your preferences are saved")
        ...     modal_form.close_modal()
        >>>
        >>> with modal_form:
        ...    st.text_input("First name", key="first_name")
        ...    st.text_input("Last name", key="last_name")
        ...    st.checkbox("I accept cookies", key="cookies")
        ...    st.experimental_modal_form_submit_button("OK", on_click=cta_callback)
        ...
        >>>
        >>> if st.button("Open modal"):
        ...     modal_form.open_modal()
        >>>
        """
        form_id = form.build_form_id(self.dg, key)

        block_dg = self.dg._block(
            ModalMixin.build_modal_proto(form_id, clear_on_submit)
        )

        # Attach the modal's button info to the newly-created block's
        # DeltaGenerator.
        block_dg._form_data = form.FormData(form_id)

        return block_dg

    @staticmethod
    def build_modal_proto(form_id: str, clear_on_submit: bool):
        block_proto = Block_pb2.Block()
        block_proto.modal.form_id = form_id
        block_proto.modal.clear_on_submit = clear_on_submit
        return block_proto

    @gather_metrics("experimental_modal_form_submit_button")
    def experimental_modal_form_submit_button(
        self,
        label: str = "Submit",
        help: Optional[str] = None,
        on_click=None,
        args=None,
        kwargs=None,
        *,  # keyword-only arguments:
        type: Literal["primary", "secondary"] = "secondary",
        disabled: bool = False,
        use_container_width: bool = False,
    ) -> bool:
        """Display a modal form submit button.

        When this button is clicked, all widget values inside the modal form will be
        sent to Streamlit in a batch.

        Every form must have a modal_form_submit_button. A modal_form_submit_button
        cannot exist outside a modal.

        Parameters
        ----------
        label : str
            A short label explaining to the user what this button is for.
            Defaults to "Submit".
        help : str or None
            A tooltip that gets displayed when the button is hovered over.
            Defaults to None.
        on_click : callable
            An optional callback invoked when this button is clicked.
        args : tuple
            An optional tuple of args to pass to the callback.
        kwargs : dict
            An optional dict of kwargs to pass to the callback.
        type : "secondary" or "primary"
            An optional string that specifies the button type. Can be "primary" for a
            button with additional emphasis or "secondary" for a normal button. This
            argument can only be supplied by keyword. Defaults to "secondary".
        disabled : bool
            An optional boolean, which disables the button if set to True. The
            default is False. This argument can only be supplied by keyword.
        use_container_width: bool
            An optional boolean, which makes the button stretch its width to match the parent container.


        Returns
        -------
        bool
            True if the button was clicked.
        """
        ctx = get_script_run_ctx()

        # Checks whether the entered button type is one of the allowed options - either "primary" or "secondary"
        if type not in ["primary", "secondary"]:
            raise StreamlitAPIException(
                'The type argument to st.button must be "primary" or "secondary". \n'
                f'The argument passed was "{type}".'
            )

        return self._modal_form_submit_button(
            label=label,
            help=help,
            on_click=on_click,
            args=args,
            kwargs=kwargs,
            type=type,
            disabled=disabled,
            use_container_width=use_container_width,
            ctx=ctx,
        )

    def _modal_form_submit_button(
        self,
        label: str = "Submit",
        help: Optional[str] = None,
        on_click=None,
        args=None,
        kwargs=None,
        *,  # keyword-only arguments:
        type: Literal["primary", "secondary"] = "secondary",
        disabled: bool = False,
        use_container_width: bool = False,
        ctx: Optional[ScriptRunContext] = None,
    ) -> bool:
        form_id = form.current_form_id(self.dg)
        submit_button_key = f"FormSubmitter:{form_id}-{label}"
        return self.dg._button(
            label=label,
            key=submit_button_key,
            help=help,
            is_form_submitter=True,
            on_click=on_click,
            args=args,
            kwargs=kwargs,
            type=type,
            disabled=disabled,
            use_container_width=use_container_width,
            ctx=ctx,
        )

    def open_modal(self):
        # use get_script_run_ctx instead of ctx, because context is dynamic and can change
        ctx = get_script_run_ctx()
        if ctx:
            ctx.enqueue(
                create_update_open_modal_id_modal_event(
                    open_modal_id=form.current_form_id(self.dg)
                )
            )

    def close_modal(self):
        # use get_script_run_ctx instead of ctx, because context is dynamic and can change
        ctx = get_script_run_ctx()
        if ctx:
            # empty open_modal_id, should effectively close the modal
            ctx.enqueue(create_update_open_modal_id_modal_event(open_modal_id=""))

    @property
    def dg(self) -> "DeltaGenerator":
        """Get our DeltaGenerator."""
        return cast(DeltaGenerator, self)
