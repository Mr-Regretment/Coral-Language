# Coral

**Coral** is a statically-typed, structured programming language that transpiles to Python.  
It bridges Python's expressiveness with the discipline of Java/C++ — explicit types, verbose functions, curly braces, C-style loops, and Java-like OOP — while keeping full access to the Python package ecosystem.

---

## Installation

```bash
pip install coral-lang
```

Or install from source:

```bash
git clone https://github.com/Mr-Regretment/Coral-Language
cd coral-lang
pip install .
```

---

## Usage

### Run a Coral file

```bash
coral run hello.coral
```

### Compile to Python (no execution)

```bash
coral compile hello.coral           # produces hello.py
coral compile hello.coral -o out.py # custom output name
```

### Inspect transpiled output

```bash
coral check hello.coral
```

### Verbose run (see the transpiled Python before it executes)

```bash
coral run hello.coral --verbose
```

---

## Language at a glance

### Variables – explicit types required

```coral
int    age    = 25;
float  price  = 9.99;
str    name   = "Coral";
bool   active = true;
list<int>      scores = [95, 87, 72];
dict<str, int> ages   = {"Alice": 30};
```

### Functions – always verbose

```coral
public int add(int a, int b) {
    return a + b;
}

private void log(str msg) {
    print("[LOG] " + msg);
}

static bool isEven(int n) {
    return n % 2 == 0;
}
```

### Control flow

```coral
// C-style for loop
for(int i = 0; i < 10; i++) {
    print(i);
}

// Foreach
foreach(str item in myList) {
    print(item);
}

// If / else if / else
if(score >= 90) {
    print("A");
} else if(score >= 80) {
    print("B");
} else {
    print("F");
}
```

### Classes and OOP

```coral
public class Animal {
    private str name;
    protected int age;

    public void __init__(str name, int age) {
        self.name = name;
        self.age  = age;
    }

    public str getName() { return self.name; }
    public void speak()  { print("..."); }
}

public class Dog extends Animal {
    private str breed;

    public void __init__(str name, int age, str breed) {
        super(name, age);
        self.breed = breed;
    }

    @Override
    public void speak() { print("Woof!"); }
}
```

### Multiple inheritance

```coral
public class ServiceDog extends Dog, Trainable {
    public void __init__(str name, int age, str breed) {
        Dog.__init__(self, name, age, breed);
        Trainable.__init__(self);
    }
}
```

### Python libraries – full ecosystem access

```coral
import numpy as np;
import pandas as pd;

list<float> data = np.array([1.5, 2.3, 3.7]);
float mean = np.mean(data);
print("Mean: " + str(mean));
```

---

## Access modifiers

| Modifier    | Meaning                                       |
|-------------|-----------------------------------------------|
| `public`    | Accessible from anywhere                      |
| `private`   | Accessible within the declaring class only    |
| `protected` | Accessible within the class and its subclasses|
| `static`    | Belongs to the class, not instances           |

---

## File extension

Coral source files use the `.coral` extension.

---

## License

MIT

