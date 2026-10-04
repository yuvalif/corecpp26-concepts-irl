# I Was Somewhat Wrong - Serialization Library

Every Ceph type that goes to disk or over the network is 
<br>
serialized with a free function `encode(value, buffer)`,
<br>
and that includes any container of any such type.

**Template resolution is a mess with `enable_if`**

---

## Slide 4.1: Detecting a Member Function

```cpp
// primary template: "no"
template <typename T, typename = void>
struct has_encode : std::false_type {};

// specialization: "yes", but only if v.encode(bl) compiles
template <typename T>
struct has_encode<T, std::void_t<decltype(
    std::declval<const T&>().encode(std::declval<bufferlist&>()))>>
  : std::true_type {};
```

---

## Slide 4.2: Numeric and Self-Encoding Types

```cpp
// numbers: copy the bytes
template <typename T>
std::enable_if_t<std::is_arithmetic_v<T>>
encode(const T& v, bufferlist& bl);

// classes that know how to encode themselves
template <typename T>
std::enable_if_t<has_encode<T>::value>          // the detector from 4.1
encode(const T& v, bufferlist& bl) { v.encode(bl); }
```

---

## Slide 4.3: Vectors

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

## Slide 4.4: Numeric Vectors

```cpp
// vector of numbers: one copy
template <typename T, typename A>
std::enable_if_t<std::is_arithmetic_v<T>>
encode(const std::vector<T, A>& v, bufferlist& bl);

// ... and again for list, set, map, deque, optional, ...
// ... and again for decode()
```

---

## Slide 4.5: Why It's a Headache

* Every pair of overloads must be made mutually exclusive **by hand**
* Forget one `!` and you get: `error: call to 'encode' is ambiguous`
* The condition hides in the return type; the same loop is written once per container

---

## Slide 4.6: Basic Encoding Concepts

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

## Slide 4.7: Range Concepts

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

## Slide 4.8: Encoding Ranges

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

## Slide 4.9: Why It's a Breeze

* No negations: `raw_bytes_range` is *more constrained* than `encodable_range`, so the compiler picks it
* One loop serves `vector`, `list`, `set`, `map`, ... and containers of containers
* The requirements self document the code

---

## Slide 4.10: Bonus: When a Type Cannot Be Encoded

```cpp
struct Tenant { uint64_t id; };            // no encode()

encode(std::vector<Tenant>{}, bl);
```

A concept can be tested right next to the type:

```cpp
static_assert(encodable<Tenant>);
// error: static assertion failed
// note: because 'Tenant' does not satisfy 'encodable'
```
