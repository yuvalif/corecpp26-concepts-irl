# What (I Was Thinking) Concepts Are Good For?

* making error messages on templates more human readable
* giving cool talks in C++ conferences

> Notes: this is where I started. The next slides show the one benefit I
> believed in, and how small it looked.

---

## Slide 1.1: A Template with an Unwritten Contract

Exposing a C++ container to Lua scripts: the library needs four static functions from the type.

```cpp
// lua_utils.h
//
// MetaTable is expected to be a class with the following members:
//   IndexClosure, NewIndexClosure, PairsClosure, LenClosure
//   (static functions that accept "lua_State*" and return "int")
template <typename MetaTable>
void create_metatable(lua_State* L) {
  set_handler(L, "__index",    MetaTable::IndexClosure);
  set_handler(L, "__newindex", MetaTable::NewIndexClosure);
  set_handler(L, "__pairs",    MetaTable::PairsClosure);
  set_handler(L, "__len",      MetaTable::LenClosure);
}
```

```cpp
// http_request_headers.cc
#include "lua_utils.h"

struct HTTPRequestHeadersMetaTable {
  static int IndexClosure(lua_State* L);
  static int NewIndexClosure(lua_State* L);
  static int LenClosure(lua_State* L);
  // oops: forgot PairsClosure
};

create_metatable<HTTPRequestHeadersMetaTable>(L);
```

* The contract lives in a comment. The compiler does not read comments.

---

## Slide 1.2: The Same Contract, as a Concept

```cpp
template <typename T>
concept lua_metatable = requires(lua_State* L) {
  { T::IndexClosure(L) }    -> std::same_as<int>;
  { T::NewIndexClosure(L) } -> std::same_as<int>;
  { T::PairsClosure(L) }    -> std::same_as<int>;
  { T::LenClosure(L) }      -> std::same_as<int>;
};

template <lua_metatable MetaTable>
void create_metatable(lua_State* L);
```

* The comment became code: it cannot go stale, and it is checked

---

## Slide 1.3: The Error Message, Without and With

Without the concept (clang 22):

```
lua_utils.h:8:43: error: no member named 'PairsClosure' in 'HTTPRequestHeadersMetaTable'
    8 |   set_handler(L, "__pairs",    MetaTable::PairsClosure);
      |                                ~~~~~~~~~~~^
http_request_headers.cc:11:3: note: in instantiation of function template specialization
                 'create_metatable<HTTPRequestHeadersMetaTable>' requested here
```

With the concept:

```
http_request_headers.cc:11:3: error: no matching function for call to 'create_metatable'
   11 |   create_metatable<HTTPRequestHeadersMetaTable>(L);
      |   ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
lua_utils.h:13:11: note: because 'HTTPRequestHeadersMetaTable' does not satisfy 'lua_metatable'
lua_utils.h:9:8: note: because 'T::PairsClosure(L)' would be invalid:
                 no member named 'PairsClosure' in 'HTTPRequestHeadersMetaTable'
```

* The error moved from the library's implementation to **my** line of code
* It names the contract that was broken, not the statement that happened to trip
* Nicer. But is it worth touching working code for?

> Notes: in an example this small, the error without the concept is already
> readable. The gap grows with the depth of the template call chain.
> That is exactly why the conclusion on the next slides sounds reasonable.
