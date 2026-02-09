import traceback

try:
    session = env['pos.session'].browse(2)
    print(f"Session: {session.name} (ID: {session.id}, State: {session.state})")
    
    # Check if custom method exists
    has_custom = hasattr(session, 'action_pos_session_close_ref')
    print(f"Has 'action_pos_session_close_ref': {has_custom}")

    # Simulation: Standard Close
    print("\n--- SIMULATION: STANDARD CLOSE ---")
    try:
        with env.cr.savepoint():
            print("Calling action_pos_session_close()...")
            # We must bypass potential 'already closed' checks if state is closing_control?
            # action_pos_session_close checks state != closed. closing_control is fine.
            session.action_pos_session_close()
            print("Standard Close Successful!")
            raise Exception("Force Rollback (Standard)")
    except Exception as e:
        if "Force Rollback" in str(e):
            print("Standard Close Logic is CLEAN.")
        else:
            print(f"!!! STANDARD CLOSE FAILED !!!: {e}")
            traceback.print_exc()

    # Simulation: Custom Close (Ref)
    if has_custom:
        print("\n--- SIMULATION: CUSTOM CLOSE (REF) ---")
        try:
            with env.cr.savepoint():
                print("Calling action_pos_session_close_ref()...")
                # Ensure context mimics frontend? 
                # balancing_account=False, amount_to_balance=0, bank_payment_method_diffs={}
                session.action_pos_session_close_ref(False, 0, {})
                print("Custom Close Successful!")
                raise Exception("Force Rollback (Custom)")
        except Exception as e:
            if "Force Rollback" in str(e):
                print("Custom Close Logic is CLEAN.")
            else:
                print(f"!!! CUSTOM CLOSE FAILED !!!: {e}")
                traceback.print_exc()
    else:
        print("\n--- SKIP CUSTOM CLOSE (Method not found in Shell) ---")
        # If method not found, print methods list to debug loading
        # print("Available methods:", dir(session))

except Exception as e:
    print(f"Script Error: {e}")
