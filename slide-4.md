# I Was Somewhat Wrong
## Serialization Library

Every Ceph type that goes to disk or over the network is
<br>
serialized with a free function `encode(value, buffer)`,
<br>
and that includes any container of any such type.

**Template resolution is a mess with `enable_if`**

---

## Slide 4.1: Encodable Types

Detecting if a type has an `encode(bufferlist&)` member:

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

Using it: `encode()` for the types that have it:

```cpp
template <typename T>
std::enable_if_t<has_encode<T>::value>
encode(const T& v, bufferlist& bl) { v.encode(bl); }
```

---

## Slide 4.2: Numeric Types

```cpp
// numbers: copy the bytes
template <typename T>
std::enable_if_t<std::is_arithmetic_v<T>>
encode(const T& v, bufferlist& bl);
```

---

## Slide 4.3: Vectors

```cpp
// vector of anything: one element at a time
template <typename T>
std::enable_if_t<!std::is_arithmetic_v<T>>  // <-- note the ! sign
encode(const std::vector<T>& v, bufferlist& bl) {
  encode(uint32_t(v.size()), bl);
  for (const auto& e : v) encode(e, bl);
}
```

---

## Slide 4.4: Numeric Vectors

```cpp
// vector of numbers: one copy
template <typename T>
std::enable_if_t<std::is_arithmetic_v<T>>
encode(const std::vector<T>& v, bufferlist& bl);
```

---

## Slide 4.5: Why the `!` Is There

Take the `!` away, and both overloads accept a vector of numbers:

```cpp
template <typename T>                       // vector of anything
void encode(const std::vector<T>& v, bufferlist& bl);

template <typename T>
std::enable_if_t<std::is_arithmetic_v<T>>   // vector of numbers
encode(const std::vector<T>& v, bufferlist& bl);

encode(std::vector<Bucket>{}, bl);   // OK: only the first one matches
encode(std::vector<int>{}, bl);      // error: call to 'encode' is ambiguous
```

The compiler cannot tell that one overload is a special case of the other

---

## Slide 4.6: Encodable Type Concept

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
  std::ranges::sized_range<R> &&            // <-- it's a range that knows its size
  encodable<std::ranges::range_value_t<R>>; // <-- its elements are encodable
  // no need to mention it's *not* a raw_bytes_range

template <typename R>
concept raw_bytes_range =
  encodable_range<R> &&                     // <-- it's an encodable range
  std::ranges::contiguous_range<R> &&       // <-- it's a contiguous range
  raw_bytes<std::ranges::range_value_t<R>>; // <-- it holds numeric values
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

## Slide 4.9: The Same Calls, with Concepts

```cpp
void encode(const encodable_range auto& r, bufferlist& bl);   // any container
void encode(const raw_bytes_range auto& r, bufferlist& bl);   // contiguous numbers

encode(std::vector<Bucket>{}, bl);   // only the first one matches
encode(std::vector<int>{}, bl);      // both match: the second one is chosen
```

`raw_bytes_range` is defined as `encodable_range && ...`,
<br>
so the compiler knows it is the special case

