# Was Really Wrong - Runtime Performance Improvement

* A concept is a question about a type that the compiler answers
* Ask the right question, and you can choose a faster implementation

> Notes: strings arriving from a Lua script are a pointer and a length - a
> `std::string_view`. Our maps are keyed by `std::string`. Every lookup built
> a temporary `std::string` (a heap allocation for any key longer than the
> small string buffer) only to throw it away.

---

## Slide 5.1: Transparent Comparators

Can compare a key with something that is not a key?

```cpp
struct no_case_less {
  using is_transparent = void;   // marking it as transparent
  bool operator()(std::string_view a, std::string_view b) const {
    return std::ranges::lexicographical_compare(a, b, {}, ::tolower, ::tolower);
  }
};

std::map<std::string, std::string>               plain;
std::map<std::string, std::string, no_case_less> headers;

std::string_view key = "ContentLength";

plain.find(key);                 // does not compile
plain.find(std::string{key});    // compiles; allocates a temporary
headers.find(key);               // compiles; no temporary
```

* `std::less<>` is the transparent comparator that comes with the standard library

> Notes: `is_transparent` is only a marker - the map checks that the name
> exists and then enables the `find()` overloads that take any type the
> comparator accepts. Without it, `find()` takes a `const std::string&` only,
> and a `string_view` does not convert to a `std::string` implicitly.

---

## Slide 5.2: Look Up a `string_view` Without Creating a `std::string`

Ask the map what it can do:

```cpp
template <typename Map>
concept finds_by_string_view =
  requires(Map& m, std::string_view key) { m.find(key); };

auto find_entry(auto& m, std::string_view key) {
  return m.find(std::string{key});   // works for every map
}

auto find_entry(finds_by_string_view auto& m, std::string_view key) {
  return m.find(key);                // used whenever it is possible
}
```

* One call, `find_entry(map, key)`, for every map type in the code base
* A map that gains a transparent comparator becomes faster with no change at the call sites
* The concept is the expression we want to write. Nothing more.

> Notes: the overload without the concept is the fallback; the constrained one
> wins whenever the map can do the lookup directly.
> The real code asks a slightly different question - "does the comparator have
> `is_transparent`?" - and selects with `if constexpr`. This version is simpler
> and also covers unordered maps.

---

## Slide 5.3: The Same Thing, Before C++20

```cpp
template <typename Map, typename = void>
struct finds_by_string_view : std::false_type {};

template <typename Map>
struct finds_by_string_view<Map, std::void_t<decltype(
    std::declval<Map&>().find(std::declval<std::string_view>()))>>
  : std::true_type {};

template <typename Map>
auto find_entry_impl(Map& m, std::string_view key, std::false_type) {
  return m.find(std::string{key});
}

template <typename Map>
auto find_entry_impl(Map& m, std::string_view key, std::true_type) {
  return m.find(key);
}

template <typename Map>
auto find_entry(Map& m, std::string_view key) {
  return find_entry_impl(m, key, finds_by_string_view<Map>{});
}
```

* It was always possible
* It was never written: the real code just called `map.find(std::string(index))`
* Concepts did not add the capability. They made it cheap enough that somebody did it.
