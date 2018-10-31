import datetime
import sys

def main():
    first_line = sys.argv[1]
    print(first_line)
    try:
        datetime.datetime.strptime(first_line, "%Y-%m-%d-%H-%M-%S.%f")
    except:
        sys.exit(1)
if __name__ == "__main__":
    main()
