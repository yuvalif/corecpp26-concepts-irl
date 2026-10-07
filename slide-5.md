# Was Really Wrong - Runtime Performance Improvement

* A concept is a question about a type that the compiler answers
* Ask the right question, and you can choose a faster implementation

---

## Slide 5.1: Transparent Comparators

Can compare a key with something that is not a key

```cpp
struct no_case_less {
  using is_transparent = void;   // marking it as transparent
  bool operator()(std::string_view a, std::string_view b) const {
    return std::ranges::lexicographical_compare(a, b, {}, ::tolower, ::tolower);
  }
};

std::map<std::string, std::string>               plain;
std::map<std::string, std::string, no_case_less> headers;
```

---

## Slide 5.2: Looking for a C String Coming from Lua

```cpp
std::string_view key = lua_tostring(L, 2);

plain.find(key);                 // does not compile
plain.find(std::string{key});    // compiles; allocates a temporary
headers.find(key);               // compiles; no temporary
```
<br>
The `std::less<>` class is the transparent comparator that comes with the standard library

---

## Slide 5.3: Look Up a `string_view` Without Creating a `std::string`

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
<br>
One call, `find_entry(map, key)`, for every map type in the code base

---

## Slide 5.4: The Same Thing, Before C++20

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
