// Use case 3: a runtime improvement.
//
// find_entry() looks up a std::string_view in any map keyed by std::string,
// and skips the temporary std::string whenever the map allows it.
//
//   (default)     the C++20 version, with a concept
//   -DPRE_CXX20   the same thing with the void_t detection idiom

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cstdio>
#include <map>
#include <string>
#include <string_view>
#include <type_traits>
#include <utility>
#include <vector>

// a transparent comparator: can compare a key with something that is not a key
struct no_case_less {
  using is_transparent = void;   // marking it as transparent
  bool operator()(std::string_view a, std::string_view b) const {
    return std::ranges::lexicographical_compare(a, b, {}, ::tolower, ::tolower);
  }
};

#ifndef PRE_CXX20

template <typename Map>
concept finds_by_string_view =
  requires(Map& m, std::string_view key) { m.find(key); };

auto find_entry(auto& m, std::string_view key) {
  return m.find(std::string{key});   // works for every map
}

auto find_entry(finds_by_string_view auto& m, std::string_view key) {
  return m.find(key);                // used whenever it is possible
}

#else

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

#endif

// --- the benchmark: the same lookups, through the same find_entry() call

constexpr int LOOKUPS = 2'000'000;

template <typename Map>
double ns_per_lookup(int size, std::string_view suffix) {
  Map m;
  std::vector<std::string> keys;
  for (int i = 0; i < size; ++i) {
    keys.push_back(std::to_string(i).append(suffix));
    m[keys.back()] = "value";
  }

  double best = 1e9;
  for (int round = 0; round < 5; ++round) {
    std::size_t found = 0;
    const auto start = std::chrono::steady_clock::now();
    for (int i = 0; i < LOOKUPS; ++i) {
      const std::string_view key = keys[i % size];
      found += find_entry(m, key) != m.end();
    }
    const auto stop = std::chrono::steady_clock::now();
    if (found != LOOKUPS) std::printf("lookup failed\n");
    best = std::min(best, std::chrono::duration<double, std::nano>(stop - start).count() / LOOKUPS);
  }
  return best;
}

void benchmark(int size, const char* kind, std::string_view suffix) {
  using plain = std::map<std::string, std::string>;
  using transparent = std::map<std::string, std::string, std::less<>>;

  const double with_temporary = ns_per_lookup<plain>(size, suffix);
  const double without = ns_per_lookup<transparent>(size, suffix);
  std::printf("%8d  %-5s  %9.1f  %12.1f  %+5.0f%%\n", size, kind, with_temporary, without,
              100 * (without - with_temporary) / with_temporary);
}

int main() {
  std::map<std::string, std::string, no_case_less> headers{{"Content-Length", "42"}};
  std::printf("case insensitive lookup: %s\n\n",
              find_entry(headers, "content-length") != headers.end() ? "found" : "missing");

  // "temporary": std::map<string, string>, find_entry() builds a std::string
  // "no temporary": the same map with std::less<>, find_entry() uses the string_view
  //
  // long keys ("42-x-amz-meta-user-defined-header") do not fit in the small
  // string buffer, so the temporary allocates. short keys ("42-etag") do fit.
  std::printf("map size  keys   temporary  no temporary  change\n");
  std::printf("                 ns/lookup     ns/lookup\n");
  for (int size : {16, 1000}) {
    benchmark(size, "long", "-x-amz-meta-user-defined-header");
    benchmark(size, "short", "-etag");
  }
}
