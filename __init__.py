// hello.coral — basic Coral features demo

public void main() {
    str name = "Coral";
    int runs = 6;

    print("Hello from " + name + "!\n");

    // C-style for loop with conditional
    for(int i = 1; i <= runs; i++) {
        if(i % 3 == 0 && i % 2 == 0) {
            print(str(i) + " → FizzBuzz");
        } else if(i % 3 == 0) {
            print(str(i) + " → Fizz");
        } else if(i % 2 == 0) {
            print(str(i) + " → Buzz");
        } else {
            print(str(i) + " → " + str(i));
        }
    }

    // Collect even numbers via foreach
    list<int> numbers = [10, 7, 4, 13, 22, 3, 8];
    list<int> evens = [];

    foreach(int n in numbers) {
        if(n % 2 == 0) {
            evens.append(n);
        }
    }

    print("\nEven numbers: " + str(evens));
}

main();
