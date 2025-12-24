
import sys
import os
import inspect

# Add current dir to path
sys.path.append(os.getcwd())

try:
    from project_x_py import ProjectX, ProjectXConfig, TradingSuite, TradingSuiteConfig
    print("✅ Imported project_x_py")
except ImportError as e:
    print(f"❌ Failed to import: {e}")
    sys.exit(1)

print("\n--- TradingSuiteConfig Inspection ---")
try:
    sig = inspect.signature(TradingSuiteConfig)
    print(f"Signature: {sig}")
    print(f"Doc: {TradingSuiteConfig.__doc__}")
except Exception as e:
    print(f"Could not inspect TradingSuiteConfig: {e}")

print("\n--- TradingSuite Inspection ---")
try:
    sig = inspect.signature(TradingSuite)
    print(f"Signature: {sig}")
    print(f"Doc: {TradingSuite.__doc__}")
except Exception as e:
    print(f"Could not inspect TradingSuite: {e}")


print("\n--- Test Instantiation ---")
class MockClient:
    def get_session_token(self): return "token"
    pass

try:
    print("Attempt 1: config=TradingSuiteConfig(instrument='MES')")
    suite = TradingSuite(
        client=MockClient(),
        realtime_client=MockClient(),
        config=TradingSuiteConfig(instrument="MES")
    )
    print("✅ Success 1")
except Exception as e:
    print(f"❌ Failed 1: {e}")

try:
    print("Attempt 2: instrument='MES' (direct arg)")
    suite = TradingSuite(
        client=MockClient(),
        realtime_client=MockClient(),
        instrument="MES"
    )
    print("✅ Success 2")
except Exception as e:
    print(f"❌ Failed 2: {e}")

