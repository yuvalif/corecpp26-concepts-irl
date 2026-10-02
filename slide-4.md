# I Was Somewhat Wrong

* Better template resolution for our serialization templates
* Still, only a compile time improvement

> Notes: all the context that is needed - every Ceph type that goes to disk or
> over the network is serialized with a free function `encode(value, buffer)`,
> and that includes any container of any such type.

---

## Slide 4.1: Overload Resolution with `enable_if`

* numeric types
* self encoding types
* vectors
* numeric vectors

---

### Slide 4.1.1: Numeric and Self-Encoding Types

```cpp
// numbers: copy the bytes
template <typename T>
std::enable_if_t<std::is_arithmetic_v<T>>
encode(const T& v, bufferlist& bl);

// classes that know how to encode themselves
template <typename T>
std::enable_if_t<has_encode<T>::value>          // void_t detector, not shown
encode(const T& v, bufferlist& bl) { v.encode(bl); }
```

---

### Slide 4.1.2: Vectors

```cpp
// vector of anything: one element at a time
template <typename T, typename A>
std::enable_if_t<!std::is_arithmetic_v<T>>  // <-- note the ! sign
encode(const std::vector<T, A>& v, bufferlist& bl) {
  encode(uint32_t(v.size()), bl);
  for (const auto& e : v) encode(e, bl);
}
```

---

### Slide 4.1.3: Numeric Vectors

```cpp
// vector of numbers: one copy
template <typename T, typename A>
std::enable_if_t<std::is_arithmetic_v<T>>
encode(const std::vector<T, A>& v, bufferlist& bl);

// ... and again for list, set, map, deque, optional, ...
// ... and again for decode()
```

---

### Slide 4.1.4: Why It's a Headache

* Every pair of overloads must be made mutually exclusive **by hand**
* Forget one `!` and you get: `error: call to 'encode' is ambiguous`
* The condition hides in the return type; the same loop is written once per container

---

## Slide 4.2: Overload Resolution with Concepts

* Basic encoding concepts
* Range concepts
* Encoding ranges

---

### Slide 4.2.1: Basic Encoding Concepts

```cpp
template <typename T>
concept raw_bytes = std::is_arithmetic_v<T>;

template <typename T>
concept self_encoding = requires(const T& v, bufferlist& bl) { v.encode(bl); };

void encode(const raw_bytes auto& v, bufferlist& bl);
void encode(const self_encoding auto& v, bufferlist& bl) { v.encode(bl); }

template <typename T>
concept encodable = requires(const T& v, bufferlist& bl) { encode(v, bl); };
```

---

### Slide 4.2.2: Range Concepts

```cpp
template <typename R>
concept encodable_range =
  std::ranges::sized_range<R> && encodable<std::ranges::range_value_t<R>>;

template <typename R>
concept raw_bytes_range =
  encodable_range<R> && std::ranges::contiguous_range<R> &&
  raw_bytes<std::ranges::range_value_t<R>>;
```

---

### Slide 4.2.3: Encoding Ranges

```cpp
// any container of anything encodable: one element at a time
void encode(const encodable_range auto& r, bufferlist& bl) {
  encode(uint32_t(std::ranges::size(r)), bl);
  for (const auto& e : r) encode(e, bl);
}

// contiguous numbers: one copy
void encode(const raw_bytes_range auto& r, bufferlist& bl);
```

---

### Slide 4.2.4: Why It's a Breeze

* No negations: `raw_bytes_range` is *more constrained* than `encodable_range`, so the compiler picks it
* One loop serves `vector`, `list`, `set`, `map`, ... and containers of containers
* The requirements self document the code

---

## Slide 4.3: When a Type Cannot Be Encoded

```cpp
struct Tenant { uint64_t id; };            // no encode()

encode(std::vector<Tenant>{}, bl);
```

---

### Slide 4.3.1: `enable_if`

* the error is inside the library, in the loop:

```
encoding.h:35:27: error: no matching function for call to 'encode'
   35 |   for (const auto& e : v) encode(e, bl);
      |                           ^~~~~~
note: candidate template ignored: requirement 'has_encode<Tenant, void>::value' was not satisfied
note: candidate template ignored: could not match 'const std::list<T, A>' against 'const Tenant'
... one note per overload ...
```

---

### Slide 4.3.2: Concepts

* the error is at my call, in my vocabulary:

```
tenant.cc:66:3: error: no matching function for call to 'encode'
   66 |   encode(std::vector<Tenant>{}, bl);
      |   ^~~~~~
note: because 'std::vector<Tenant>' does not satisfy 'encodable_range'
note: because 'Tenant' does not satisfy 'encodable'
```

> Notes: the messages are trimmed to the relevant lines. In full, the concepts
> error is not shorter than the `enable_if` one, because every rejected
> overload now explains itself. The win is where the error points and what it
> names, not its length.

---

### Slide 4.3.3: A Concept Can Be Tested

* right next to the type:

```cpp
static_assert(encodable<Tenant>);
// error: static assertion failed
// note: because 'Tenant' does not satisfy 'encodable'
```

> Notes: a concept is a compile time predicate, so it can be asserted like any
> other. The error is three lines long.
>
> Bridge to the next section: still, all of this happens at compile time.
> The binary is the same.
