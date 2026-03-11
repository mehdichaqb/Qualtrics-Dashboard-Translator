st.subheader("Translation Provider")
provider_choice = st.selectbox(
"Provider",
        options=["Auto (Anthropic if key set)", "Anthropic API", "Mock (for testing)"],
        options=[
            "Argos Translate - Offline (Recommended)",
            "Anthropic API (requires key)",
            "Mock (for testing)",
        ],
index=0,
)
    if "Anthropic" in provider_choice and "Auto" not in provider_choice:
    if "Argos" in provider_choice:
        provider = "argos"
    elif "Anthropic" in provider_choice:
provider = "anthropic"
elif "Mock" in provider_choice:
provider = "mock"
else:
provider = "auto"

    api_key = st.text_input(
        "Anthropic API Key (or set ANTHROPIC_API_KEY env var)",
        type="password",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
    )
    api_key = ""
    if provider == "anthropic":
        api_key = st.text_input(
            "Anthropic API Key (or set ANTHROPIC_API_KEY env var)",
            type="password",
            value=os.environ.get("ANTHROPIC_API_KEY", ""),
        )

# ── Main: File Uploaders ─────────────────────────────────────────────────
st.header("1. Upload Files")
