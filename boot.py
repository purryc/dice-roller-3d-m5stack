try:
    import os

    try:
        os.remove("boot_error.txt")
    except Exception:
        pass

    import main

    main.run()
except Exception:
    try:
        import traceback

        f = open("boot_error.txt", "w")
        traceback.print_exc(file=f)
        f.close()
    except Exception:
        pass
    raise
