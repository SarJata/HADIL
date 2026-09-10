import os
import sys

# Clear OPENAI_API_KEY from environment before any imports/dotenv loading
os.environ.pop("OPENAI_API_KEY", None)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_hadil_imports_without_openai_api_key():
    """
    Regression test ensuring that HADIL backend, API routes, and AI modules can be imported
    and initialized without requiring an OPENAI_API_KEY environment variable.
    """
    old_key = os.environ.get("OPENAI_API_KEY")
    try:
        # Ensure OPENAI_API_KEY is not set
        os.environ.pop("OPENAI_API_KEY", None)
        
        # Import core modules
        import ai_modules.interpreter
        import ai_modules.followup_generator
        import ai_modules.context_analyzer
        import ai_modules.generator
        import ai_modules.verifier
        import ai_modules.providers
        import services.onboarding_service
        import routes.api
        import main
        
        # Verify that importing interpreter doesn't define a top-level OpenAI client requiring API key
        assert not hasattr(ai_modules.interpreter, "client")
        assert not hasattr(ai_modules.followup_generator, "client")
        assert not hasattr(ai_modules.context_analyzer, "client")
        
        # Verify OpenAIProvider can be instantiated without key until actual API calls
        provider = ai_modules.providers.OpenAIProvider(api_key="")
        assert provider.api_key == ""
        
        # Health check on unconfigured provider returns clean error dict, not unhandled exception
        health = provider.health_check()
        assert health["success"] is False
        assert "required" in health["message"].lower() or "missing" in health["message"].lower()
    finally:
        if old_key is not None:
            os.environ["OPENAI_API_KEY"] = old_key


if __name__ == "__main__":
    test_hadil_imports_without_openai_api_key()
    print("PASS: HADIL import regression test without OPENAI_API_KEY succeeded!")
