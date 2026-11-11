import sys

if __name__ == '__main__':
    if sys.argv[1:2] == ['--atelier-worker']:
        del sys.argv[1]
        from atelier.workers.entry import main
        main()
    else:
        from atelier.app.window import run
        run()
