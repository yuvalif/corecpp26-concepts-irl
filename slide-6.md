# Convert an Infinite Loop to a Compile Time Error

* Some bugs are a property of the *type*, not of the values
* A concept can turn "works with any container (almost)" into a rule the compiler enforces

---

## Slide 6.1: Stateless Iterators

A script iterates over a C++ container that we expose to it:

```lua
for key, value in pairs(RequestHeaders) do
  print(key, value)
end
```
<br>
Since `RequestHeaders` is a C++ container pretending to be a Lua table,
<br>
we supply our own `next()` function, through the table's `__pairs` metamethod.

---

## Slide 6.2: C++ Binding for the `next()` Function

Lua drives the loop by calling `key, value = next(table, key)`, again and again:

```cpp
template <typename Map>
int next(lua_State* L) {
  auto& m = get_table<Map>(L);             // stored as opaque user data
  auto it = m.begin();
  // nil key marks the start of the loop
  // if key is nil, continue at line 13
  if (!lua_isnil(L, 2)) {
    const char* key = lua_tostring(L, 2);  // get the input "key" parameter
    it = m.find(key);                      // find the key we returned last time
    if (it != m.end()) ++it;               // ... and step to the one after it
  }
  // in Lua you push values to a stack to return them
  if (it == m.end()) {                     // end of the loop
    lua_pushnil(L);                        // return nil key
    lua_pushnil(L);                        // and nil value
  } else {
    lua_pushstring(L, it->first.c_str());  // return the next key
    lua_pushstring(L, it->second.c_str()); // return the next value
  }
  return 2;                                // returning 2 things: key, value
}
```

---

## Slide 6.3: The Infinite Loop

Now we use the template with a container that allows duplicate keys:

```cpp
std::multimap<std::string, std::string> unlucky_headers{
  {"accept", "text/html"},
  {"accept", "application/json"},
  {"host",   "ceph.io"}};

expose(L, "RequestHeaders", unlucky_headers);   // pairs() will use next<multimap>
```

---

## Slide 6.4: The Script Never Returns

The Lua code:
```lua
for key, value in pairs(RequestHeaders) do
  print(key, value)
end
```

What it prints:
```
accept  text/html
accept  application/json
accept  application/json
accept  application/json
... (forever)
```

---

## Slide 6.5: Make It a Compile Time Error

"Stateless iteration needs unique keys"
<br>
The standard containers already tell us which is which:

```cpp
std::map<K, V>::insert(value)       // returns std::pair<iterator, bool>
std::multimap<K, V>::insert(value)  // returns iterator: no boolean, no failure on duplicate keys
```

---

## Slide 6.6: The `unique_keys` Concept

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

---

## Slide 6.7: Compile Time Error vs. Infinite Loop

```
error: no matching function for call to 'expose'
   97 |   expose(L, "RequestHeaders", unlucky_headers);
      |   ^~~~~~
note: candidate template ignored: constraints not satisfied
      [with Map = std::multimap<std::string, std::string>]
note: because 'std::multimap<std::string, std::string>' does not satisfy 'unique_keys'
```

