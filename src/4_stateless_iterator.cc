// Use case 4: an infinite loop becomes a compile time error.
//
// A stateless next(): find the key the script got last time, and return the
// entry after it. Correct only for containers with unique keys.
//
//   (default)       runs: fine on a map, loops forever on a multimap
//   -DUNIQUE_KEYS   constrain next() and expose(): the multimap does not compile

#include <concepts>
#include <map>
#include <string>
#include <utility>

#include <lua.hpp>

#ifdef UNIQUE_KEYS
template <typename C>
concept unique_keys = requires(C& c, typename C::value_type v) {
  { c.insert(v) } -> std::same_as<std::pair<typename C::iterator, bool>>;
};
#define CONTAINER unique_keys
#else
#define CONTAINER typename
#endif

// Lua keeps a pointer to the C++ container next to the function it calls
template <typename Map>
Map& get_table(lua_State* L) {
  return *static_cast<Map*>(lua_touserdata(L, lua_upvalueindex(1)));
}

template <CONTAINER Map>
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

// the __pairs metamethod: what pairs(table) returns to the "for" loop
template <CONTAINER Map>
int pairs(lua_State* L) {
  lua_pushvalue(L, lua_upvalueindex(1));   // pass the container on to next()
  lua_pushcclosure(L, next<Map>, 1);       // the iteration function
  lua_pushvalue(L, 1);                     // the table
  lua_pushnil(L);                          // the first key
  return 3;
}

// make the container visible to scripts, as a global table called "name"
template <CONTAINER Map>
void expose(lua_State* L, const char* name, Map& m) {
  lua_newtable(L);                         // the table
  lua_newtable(L);                         // its metatable
  lua_pushlightuserdata(L, &m);
  lua_pushcclosure(L, pairs<Map>, 1);
  lua_setfield(L, -2, "__pairs");
  lua_setmetatable(L, -2);
  lua_setglobal(L, name);
}

// the loop of the slides, plus a way out of it
const char* script = R"lua(
  local count = 0
  print("HTTP Headers:")
  for key, value in pairs(RequestHeaders) do
    print(key, value)
    count = count + 1
    if count == 20 then print("... (forever)") break end
  end
)lua";

int main() {
  lua_State* L = luaL_newstate();
  luaL_openlibs(L);

  std::multimap<std::string, std::string> lucky_headers{
    {"accept", "text/html"},
    {"host",   "ceph.io"}};
  expose(L, "RequestHeaders", lucky_headers);
  luaL_dostring(L, script);

  std::multimap<std::string, std::string> unlucky_headers{
    {"accept", "text/html"},
    {"accept", "application/json"},
    {"host",   "ceph.io"}};
  expose(L, "RequestHeaders", unlucky_headers);
  luaL_dostring(L, script);

  lua_close(L);
}
