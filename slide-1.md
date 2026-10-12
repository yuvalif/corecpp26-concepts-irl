# What (I Was Thinking) Concepts Are Good For?

* Making error messages on templates more human readable
* Giving cool talks in C++ conferences

---

## Slide 1.1: A Template with Unwritten Requirements

Exposing a C++ container to Lua scripts:
<br>
The library needs four static functions from the type

```cpp
// lua_utils.h
//
// M is expected to be a class with the following members:
//   IndexClosure, NewIndexClosure, PairsClosure, LenClosure
//   (static functions that accept "lua_State*" and return "int")
template <typename M>
void create_metatable(lua_State* L) {
  set_handler(L, "__index",    M::IndexClosure);    // <-- expecting M::IndexClosure static member
  set_handler(L, "__newindex", M::NewIndexClosure); // <-- expecting M::NewIndexClosure static member
  set_handler(L, "__pairs",    M::PairsClosure);    // <-- expecting M::PairsClosure static member
  set_handler(L, "__len",      M::LenClosure);      // <-- expecting M::LenClosure static member
}
```

---

## Slide 1.2: Using the Template for HTTP Request Headers

```cpp
// http_request_headers.cc
#include "lua_utils.h"

struct HTTPRequestHeadersMetaTable {
  static int IndexClosure(lua_State* L);
  static int NewIndexClosure(lua_State* L);
  static int LenClosure(lua_State* L);
  // oops: forgot PairsClosure
};

// trying to create a metatable of type HTTPRequestHeadersMetaTable
create_metatable<HTTPRequestHeadersMetaTable>(L);
```
<br>
The requirements on the struct live in a comment

---

## Slide 1.3: The Error Message

```
lua_utils.h:8:35: error: no member named 'PairsClosure' in 'HTTPRequestHeadersMetaTable'
    8 |   set_handler(L, "__pairs",    M::PairsClosure);
      |                                ~~~^
http_request_headers.cc:11:3: note: in instantiation of function template specialization
                 'create_metatable<HTTPRequestHeadersMetaTable>' requested here
```

---

## Slide 1.4: The Same Requirements, as a Concept

```cpp
template <typename T>
concept lua_metatable = requires(lua_State* L) {
  { T::IndexClosure(L) }    -> std::same_as<int>;
  { T::NewIndexClosure(L) } -> std::same_as<int>;
  { T::PairsClosure(L) }    -> std::same_as<int>;
  { T::LenClosure(L) }      -> std::same_as<int>;
};

template <lua_metatable M>
void create_metatable(lua_State* L); // <-- same implementation as before

// trying to create a metatable of type HTTPRequestHeadersMetaTable
// still failing, but with a better error message
create_metatable<HTTPRequestHeadersMetaTable>(L);
```
<br>
The comment is now code

---

## Slide 1.5: The Error Message, with a Concept

```
http_request_headers.cc:11:3: error: no matching function for call to 'create_metatable'
   11 |   create_metatable<HTTPRequestHeadersMetaTable>(L);
      |   ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
lua_utils.h:13:11: note: because 'HTTPRequestHeadersMetaTable' does not satisfy 'lua_metatable'
lua_utils.h:9:8: note: because 'T::PairsClosure(L)' would be invalid:
                 no member named 'PairsClosure' in 'HTTPRequestHeadersMetaTable'
```

* The error moved from the library's implementation to the line of code where the problem occurred
* It names the requirement that was broken, not the statement that happened to trip
<br>
<br>
### Nicer. But is it worth touching working code for?
