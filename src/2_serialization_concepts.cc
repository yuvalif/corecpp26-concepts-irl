// Use case 2, after: overload resolution with concepts.
//
//   (default)        compiles and runs
//   -DNOT_ENCODABLE  encode a type that has no encode()
//   -DASSERT         the same, caught by a static_assert next to the type

#include <concepts>
#include <cstdint>
#include <cstdio>
#include <list>
#include <map>
#include <ranges>
#include <set>
#include <string>
#include <utility>
#include <vector>

#include "bufferlist.h"

template <typename T>
concept raw_bytes = std::is_arithmetic_v<T>;

template <typename T>
concept self_encoding = requires(const T& v, bufferlist& bl) { v.encode(bl); };

void encode(const raw_bytes auto& v, bufferlist& bl) {
  bl.append(&v, sizeof(v));
}
void encode(const self_encoding auto& v, bufferlist& bl) { v.encode(bl); }

template <typename T>
concept encodable = requires(const T& v, bufferlist& bl) { encode(v, bl); };

// not on the slides: a map is a range of pairs
template <encodable A, encodable B>
void encode(const std::pair<A, B>& p, bufferlist& bl) {
  encode(p.first, bl);
  encode(p.second, bl);
}

template <typename R>
concept encodable_range =
  std::ranges::sized_range<R> && encodable<std::ranges::range_value_t<R>>;

template <typename R>
concept raw_bytes_range =
  encodable_range<R> && std::ranges::contiguous_range<R> &&
  raw_bytes<std::ranges::range_value_t<R>>;

// any container of anything encodable: one element at a time
void encode(const encodable_range auto& r, bufferlist& bl) {
  encode(uint32_t(std::ranges::size(r)), bl);
  for (const auto& e : r) encode(e, bl);
}

// contiguous numbers: one copy
void encode(const raw_bytes_range auto& r, bufferlist& bl) {
  encode(uint32_t(std::ranges::size(r)), bl);
  bl.append(std::ranges::data(r),
            std::ranges::size(r) * sizeof(std::ranges::range_value_t<decltype(r)>));
}

struct Bucket {
  uint64_t id;
  void encode(bufferlist& bl) const { ::encode(id, bl); }
};

struct Tenant { uint64_t id; };            // no encode()

static_assert(encodable<Bucket>);
static_assert(!encodable<Tenant>);
static_assert(raw_bytes_range<std::vector<int>>);
static_assert(!raw_bytes_range<std::list<int>>);
#ifdef ASSERT
static_assert(encodable<Tenant>);
#endif

int main() {
  bufferlist bl;
  encode(42, bl);
  encode(Bucket{1}, bl);
  encode(std::vector<int>{1, 2, 3}, bl);
  encode(std::string{"contiguous numbers too"}, bl);
  encode(std::vector<Bucket>{{1}, {2}}, bl);
  encode(std::list<std::vector<Bucket>>{{{1}}, {{2}, {3}}}, bl);
  encode(std::map<int, std::set<std::string>>{{1, {"a", "b"}}}, bl);
#ifdef NOT_ENCODABLE
  encode(std::vector<Tenant>{}, bl);
#endif
  std::printf("encoded %zu bytes\n", bl.bytes.size());
}
