# Convert an Infinite Loop to a Compile Time Error

* Some bugs are a property of the *type*, not of the values
* A concept can turn "works with any container (almost)" into a rule the compiler enforces

---

## Slide 6.1: Stateless Iterators

A script iterates over a C++ container that we expose to it:

```lua
for key, value in pairs(HTTP.RequestHeaders) do
  print(key, value)
end
```
<br>
Since `HTTP.RequestHeaders` is a C++ container pretending to be a Lua table,
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
  if (!lua_isnil(L, 2)) {                  // nil key marks the start of the loop
    it = m.find(lua_tostring(L, 2));       // find the key we returned last time
    if (it != m.end()) ++it;               // ... and step to the one after it
  }
  if (it == m.end()) {                     // in Lua you push values to a stack to return them
    lua_pushnil(L);                        // end of the loop: return nil key
    lua_pushnil(L);                        // return nil value
  } else {
    lua_pushstring(L, it->first.c_str());  // return the key
    lua_pushstring(L, it->second.c_str()); // return the value
  }
  return 2;                                // returning 2 things: key, value
}
```

---

## Slide 6.3: Why Not Keep a C++ Iterator Between the Calls?

* The script may never finish the loop (`break`, error): who releases the iterator?
* The script may change the container in the middle of the loop: the iterator is invalid
* A key is just a value. It has no lifetime and cannot dangle.

---

## Slide 6.4: The Infinite Loop

Now we use the template with a container that allows duplicate keys:

```cpp
std::multimap<std::string, std::string> headers{
  {"accept", "text/html"},
  {"accept", "application/json"},
  {"host",   "ceph.io"}};

expose(L, "RequestHeaders", headers);   // pairs() will use next<multimap>
```

---

## Slide 6.5: The Script Never Returns

```
accept  text/html
accept  application/json
accept  application/json
accept  application/json
... (forever)
```

---

## Slide 6.6: Why It Loops

* `find("accept")` returns the first "accept". The next entry is the second one.
* Its key is also "accept". So `find()` goes back to the first...
* It compiles, and it passes every test that has no duplicate keys
* Same with `std::multiset`

---

## Slide 6.7: Make It a Compile Time Error

"Stateless iteration needs unique keys"
<br>
the standard containers already tell us which is which:

```cpp
std::map<K, V>::insert(value)       // returns std::pair<iterator, bool>
std::multimap<K, V>::insert(value)  // returns iterator
```

---

## Slide 6.8: The `unique_keys` Concept

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

## Slide 6.9: Compile Time Error vs. Infinite Loop

```
error: no matching function for call to 'expose'
   78 |   expose(L, "RequestHeaders", headers);
      |   ^~~~~~
note: candidate template ignored: constraints not satisfied
      [with Map = std::multimap<std::string, std::string>]
note: because 'std::multimap<std::string, std::string>' does not satisfy 'unique_keys'
```

