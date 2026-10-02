# Convert an Infinite Loop to a Compile Time Error

* Some bugs are a property of the *type*, not of the values
* A concept can turn "works with any container (almost)" into a rule the compiler enforces

---

## Slide 6.1: Stateless Iterators

* The Lua script
* C++ binding for `next()`
* Why not keep a C++ iterator between the calls?

---

### Slide 6.1.1: The Lua Script

A script iterates over a C++ container that we expose to it:

```lua
for key, value in pairs(HTTP.RequestHeaders) do
  print(key, value)
end
```

Since `HTTP.RequestHeaders` is a C++ container pretending to be a Lua table,
we supply our own `next()` function, through the table's `__pairs` metamethod.

---

### Slide 6.1.2: C++ Binding for the `next()` Function

Lua drives the loop by calling `key, value = next(table, key)`, again and again:

```cpp
template <typename Map>
int next(lua_State* L) {
  auto& m = get_table<Map>(L);          // stored as opaque user data
  auto it = m.begin();
  if (!lua_isnil(L, 2)) {               // nil key: start of the loop
    it = m.find(lua_tostring(L, 2));    // find the key we returned last time
    if (it != m.end()) ++it;            // ... and step to the one after it
  }
  if (it == m.end()) {
    lua_pushnil(L);                     // end of the loop: return nil, nil
    lua_pushnil(L);
  } else {
    lua_pushstring(L, it->first.c_str());
    lua_pushstring(L, it->second.c_str());
  }
  return 2;                             // returning 2 values: key, value
}
```

> Notes: walk through the code comments - find the key we returned last time,
> step to the next entry, return its key and value. The script holds the key
> between calls; we hold nothing.
> `lua_push...` pushes a value to the Lua "stack"; the pushed values are what
> the function returns to the script.

---

### Slide 6.1.3: Why Not Keep a C++ Iterator Between the Calls?

* The script may never finish the loop (`break`, error): who releases the iterator?
* The script may change the container in the middle of the loop: the iterator is invalid
* A key is just a value. It has no lifetime and cannot dangle.

---

## Slide 6.2: The Infinite Loop

Now we use the template with a container that allows duplicate keys:

```cpp
std::multimap<std::string, std::string> headers{
  {"accept", "text/html"},
  {"accept", "application/json"},
  {"host",   "ceph.io"}};

expose(L, "RequestHeaders", headers);   // pairs() will use next<multimap>
```

---

### Slide 6.2.1: The Script Never Returns

```
accept  text/html
accept  application/json
accept  application/json
accept  application/json
... (forever)
```

> Notes: this is the output of the script from 6.1.1, running over the
> multimap. In production it is a script that never returns, inside a storage
> daemon.

---

### Slide 6.2.2: Why It Loops

* `find("accept")` returns the first "accept". The next entry is the second one.
* Its key is also "accept". So `find()` goes back to the first...
* It compiles, and it passes every test that has no duplicate keys
* Same with `std::multiset`

---

## Slide 6.3: Make It a Compile Time Error

"Stateless iteration needs unique keys" - the standard containers already tell us which is which:

```cpp
std::map<K, V>::insert(value)       // returns std::pair<iterator, bool>
std::multimap<K, V>::insert(value)  // returns iterator
```

---

### Slide 6.3.1: The `unique_keys` Concept

```cpp
template <typename C>
concept unique_keys = requires(C& c, typename C::value_type v) {
  { c.insert(v) } -> std::same_as<std::pair<typename C::iterator, bool>>;
};

template <unique_keys Map>
int next(lua_State* L);

template <unique_keys Map>
void expose(lua_State* L, const char* name, Map& m);
```

> Notes: `unique_keys` holds for `map`, `set` and `unordered_map`, and fails
> for `multimap` and `multiset`.
> The constraint is on `expose()` too, on purpose: nobody calls `next<Map>`
> directly, we only hand its address to Lua. Constraining the function the
> developer actually calls is what produces a readable error.

---

### Slide 6.3.2: The Error

```
error: no matching function for call to 'expose'
   78 |   expose(L, "RequestHeaders", headers);
      |   ^~~~~~
note: candidate template ignored: constraints not satisfied
      [with Map = std::multimap<std::string, std::string>]
note: because 'std::multimap<std::string, std::string>' does not satisfy 'unique_keys'
```

---

### Slide 6.3.3: What We Gained

* The bug cannot be written any more
* No test needed, no code review comment needed, no production incident needed
* The concept documents *why*: the algorithm, not the container, has the requirement
