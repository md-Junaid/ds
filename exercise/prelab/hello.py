import sys

def repeat(s, exclaim):
    result = s + s + s
    if exclaim:
        result = result + '!!!'
    return result

def main():
    print('Hello there', sys.argv[1])
    print(repeat('Hey', False))
    print(repeat('Woo Hoo', True))

if __name__ == '__main__':
    main()