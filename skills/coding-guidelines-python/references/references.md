# References

Authoritative sources backing the four principles in this skill.

---

## Think Before Coding

**The Pragmatic Programmer** — Hunt & Thomas
Chapters on "tracer bullets" and estimating: clarify what you're building before building it.
https://pragprog.com/titles/tpp20/the-pragmatic-programmer-20th-anniversary-edition/

**Specification by Example** — Gojko Adzic
Living documentation: define acceptance criteria before implementation.
https://gojko.net/books/specification-by-example/

---

## Simplicity First

**YAGNI — You Aren't Gonna Need It** (XP principle, Ron Jeffries)
Don't add functionality until it's needed. Every line of unused code is a liability.
https://martinfowler.com/bliki/Yagni.html

**KISS — Keep It Simple, Stupid**
Simplicity should be a key goal; unnecessary complexity should be avoided.
https://en.wikipedia.org/wiki/KISS_principle

**Rule of Three** — Martin Fowler (Refactoring)
Abstraction is justified only when you have three concrete uses, not one or two.
https://en.wikipedia.org/wiki/Rule_of_three_(computer_programming)

**The Zen of Python** — Tim Peters (PEP 20)
"Simple is better than complex. Complex is better than complicated."
https://peps.python.org/pep-0020/

---

## Surgical Changes

**Refactoring: Improving the Design of Existing Code** — Martin Fowler
Small, behavior-preserving transformations. Each step leaves the system working.
https://martinfowler.com/books/refactoring.html

**The Boy Scout Rule** (Clean Code) — Robert C. Martin
Leave the code cleaner than you found it — but only the specific spot you touched.
https://www.oreilly.com/library/view/97-things-every/9780596809515/ch08.html

**Connascence** — Meilir Page-Jones
A framework for reasoning about coupling; surgical changes minimize connascence spread.
https://connascence.io/

---

## Goal-Driven Execution

**Test-Driven Development: By Example** — Kent Beck
Red → Green → Refactor. Every change is motivated by a failing test.
https://www.oreilly.com/library/view/test-driven-development/0321146530/

**Growing Object-Oriented Software, Guided by Tests** — Freeman & Pryce
Start from acceptance tests that define the goal; work inward.
https://www.growing-object-oriented-software.com/

**Transformation Priority Premise** — Robert C. Martin
Ranked list of code transformations that keep tests passing with minimal leaps.
https://blog.cleancoder.com/uncle-bob/2013/05/27/TheTransformationPriorityPremise.html

---

## General

**SOLID Principles** — Robert C. Martin
When abstractions ARE warranted, SOLID gives the vocabulary: SRP, OCP, LSP, ISP, DIP.
https://en.wikipedia.org/wiki/SOLID

**A Philosophy of Software Design** — John Ousterhout
"Complexity is anything that makes a system hard to understand or modify." Deep modules > shallow.
https://web.stanford.edu/~ouster/cgi-bin/book.php
