import sys
import os
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.tools.navigation import fast_lookup_route
from app.models.navigation import NavigationItem

async def test():
    # Mocking session
    class MockSession:
        async def execute(self, stmt):
            class MockResult:
                def scalars(self):
                    class MockScalars:
                        def all(self):
                            return [
                                NavigationItem(label="List", path="/bank/payment_voucher_list", parents=["Bank", "Payment", "Voucher"], client_id=4),
                                NavigationItem(label="List", path="/bank/save_payment_voucher_list", parents=["Bank", "Save", "Payment", "Voucher"], client_id=4, is_custom=True),
                                NavigationItem(label="List", path="/bank/edit_payment_voucher_list", parents=["Bank", "Edit", "Payment", "Voucher"], client_id=4, is_custom=True),
                                NavigationItem(label="List", path="/bank/update_payment_voucher_list", parents=["Bank", "Update", "Payment", "Voucher"], client_id=4, is_custom=True),
                            ]
                    return MockScalars()
            return MockResult()
            
    session = MockSession()
    path, ambiguous = await fast_lookup_route("paymen voucher list", session, 4)
    if path:
        print(f"Path: {path}")
    if ambiguous:
        print("Ambiguous:")
        for cand in ambiguous:
            print(f"- {cand['path']}")

if __name__ == "__main__":
    asyncio.run(test())
