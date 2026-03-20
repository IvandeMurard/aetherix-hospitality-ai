"""Settings view - restaurant profile configuration."""

import streamlit as st
import requests

from config import get_text, API_BASE


def render_settings_view(context: dict) -> None:
    """Render the settings page with restaurant profile form."""
    lang = context["language"]
    st.title(get_text("nav.settings", lang))

    try:
        response = requests.get(
            f"{API_BASE}/api/restaurant/profiles", timeout=5
        )
        profiles = response.json() if response.status_code == 200 else []
    except Exception:
        profiles = []
        st.warning("Unable to connect to backend. Settings will not be saved.")

    existing_profile = profiles[0] if profiles else None

    industry_defaults = st.session_state.get("industry_defaults")
    if industry_defaults:
        form_defaults = {**(existing_profile or {}), **industry_defaults}
        if "industry_defaults" in st.session_state:
            del st.session_state["industry_defaults"]
    else:
        form_defaults = existing_profile or {}

    def _val(key: str, default):
        return form_defaults.get(key, default)

    def _int(key: str, default: int) -> int:
        v = _val(key, default)
        return int(v) if v is not None else default

    with st.form("restaurant_profile_form"):
        st.subheader("Restaurant Profile")
        col1, col2 = st.columns(2)

        with col1:
            property_name = st.text_input(
                "Property Name",
                value=_val("property_name", ""),
                placeholder="The Grand Hotel",
            )
            outlet_name = st.text_input(
                "Restaurant Name",
                value=_val("outlet_name", ""),
                placeholder="Main Restaurant",
            )

        with col2:
            total_seats = st.number_input(
                "Total Seats",
                min_value=1,
                value=_int("total_seats", 80),
            )
            outlet_options = ["restaurant", "bar", "room_service", "pool_bar"]
            outlet_type_val = _val("outlet_type", "restaurant")
            outlet_index = (
                outlet_options.index(outlet_type_val)
                if outlet_type_val in outlet_options
                else 0
            )
            outlet_type = st.selectbox(
                "Type",
                options=outlet_options,
                index=outlet_index,
            )

        st.divider()
        st.subheader("Business Thresholds")
        col1, col2 = st.columns(2)
        with col1:
            breakeven_covers = st.number_input(
                "Break-even Covers",
                min_value=0,
                value=_int("breakeven_covers", 35),
                help="Minimum covers needed to cover fixed costs",
            )
        with col2:
            target_covers = st.number_input(
                "Target Covers",
                min_value=0,
                value=_int("target_covers", 60),
                help="Ideal covers for profitable service",
            )

        st.divider()
        st.subheader("Staffing Ratios")
        st.caption("How many covers can each staff member handle?")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            covers_per_server = st.number_input(
                "Per Server",
                min_value=1,
                value=_int("covers_per_server", 16),
            )
        with col2:
            covers_per_host = st.number_input(
                "Per Host",
                min_value=1,
                value=_int("covers_per_host", 60),
            )
        with col3:
            covers_per_runner = st.number_input(
                "Per Runner",
                min_value=1,
                value=_int("covers_per_runner", 40),
            )
        with col4:
            covers_per_kitchen = st.number_input(
                "Per Kitchen",
                min_value=1,
                value=_int("covers_per_kitchen", 30),
            )

        col1, col2 = st.columns(2)
        with col1:
            min_foh_staff = st.number_input(
                "Minimum FOH Staff",
                min_value=1,
                value=_int("min_foh_staff", 2),
            )
        with col2:
            min_boh_staff = st.number_input(
                "Minimum Kitchen Staff",
                min_value=1,
                value=_int("min_boh_staff", 2),
            )

        st.divider()
        st.subheader("Integrations")
        st.caption("COMING SOON", help="Connect your PMS and POS for automatic data sync")
        col1, col2 = st.columns(2)
        with col1:
            st.checkbox("Mews PMS", disabled=True)
            st.checkbox("Opera PMS", disabled=True)
        with col2:
            st.checkbox("Lightspeed POS", disabled=True)
            st.checkbox("Toast POS", disabled=True)

        st.markdown("---")
        submitted = st.form_submit_button("Save Changes", type="primary")

        if submitted:
            profile_data = {
                "property_name": property_name,
                "outlet_name": outlet_name,
                "outlet_type": outlet_type,
                "total_seats": total_seats,
                "breakeven_covers": breakeven_covers,
                "target_covers": target_covers,
                "covers_per_server": covers_per_server,
                "covers_per_host": covers_per_host,
                "covers_per_runner": covers_per_runner,
                "covers_per_kitchen": covers_per_kitchen,
                "min_foh_staff": min_foh_staff,
                "min_boh_staff": min_boh_staff,
            }
            try:
                if existing_profile:
                    response = requests.put(
                        f"{API_BASE}/api/restaurant/profile/{existing_profile['id']}",
                        json=profile_data,
                        timeout=10,
                    )
                else:
                    response = requests.post(
                        f"{API_BASE}/api/restaurant/profile",
                        json=profile_data,
                        timeout=10,
                    )
                if response.status_code in [200, 201]:
                    st.success("Settings saved successfully!")
                    st.rerun()
                else:
                    st.error(f"Error saving settings: {response.text}")
            except Exception as e:
                st.error(f"Connection error: {e}")

    st.markdown("---")
    st.caption("Not sure about staffing ratios?")
    col1, col2, col3 = st.columns(3)

    def _apply_defaults(restaurant_type: str):
        try:
            resp = requests.get(
                f"{API_BASE}/api/restaurant/defaults/{restaurant_type}",
                timeout=5,
            )
            if resp.status_code == 200:
                st.session_state["industry_defaults"] = resp.json()
                st.rerun()
            else:
                st.error(f"Could not load defaults: {resp.text}")
        except Exception as e:
            st.error(f"Connection error: {e}")

    with col1:
        if st.button("Use Fine Dining Defaults"):
            _apply_defaults("fine_dining")
    with col2:
        if st.button("Use Casual Dining Defaults"):
            _apply_defaults("casual_dining")
    with col3:
        if st.button("Use Hotel Restaurant Defaults"):
            _apply_defaults("hotel_restaurant")
