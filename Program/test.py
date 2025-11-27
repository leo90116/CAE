import subprocess


def main():
    a = int(input("Enter a number: "))
    check_status()
    if a % 2 == 0:
        print("Its even")
    else:
        print("Its odd")


main()
