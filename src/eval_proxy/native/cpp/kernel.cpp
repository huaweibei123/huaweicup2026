#include <algorithm>
#include <charconv>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <utility>
#include <vector>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

namespace {

using U64 = std::uint64_t;

struct Candidate {
    std::string id;
    U64 pipe_bound_q6;
    U64 dependency_bound_q6;
    U64 copy_bytes;
    U64 bandwidth;
    U64 cross_task_count;
    U64 cross_core_count;
    U64 imbalance_ppm;
};

struct Ranked {
    std::string id;
    U64 compute_q6;
    U64 transfer_q6;
    U64 communication_penalty_q6;
    U64 imbalance_penalty_q6;
    U64 score_q6;
};

[[noreturn]] void fail(const std::string& message) {
    throw std::runtime_error(message);
}
U64 checked_add(U64 left, U64 right, const char* label) {
    if (right > std::numeric_limits<U64>::max() - left) {
        fail(std::string("overflow while computing ") + label);
    }
    return left + right;
}

U64 checked_mul(U64 left, U64 right, const char* label) {
    if (left != 0 && right > std::numeric_limits<U64>::max() / left) {
        fail(std::string("overflow while computing ") + label);
    }
    return left * right;
}

U64 parse_u64(const std::string& text, std::size_t line_number) {
    if (text.empty()) {
        fail("line " + std::to_string(line_number) + ": empty numeric field");
    }
    U64 value = 0;
    const auto result = std::from_chars(text.data(), text.data() + text.size(), value);
    if (result.ec != std::errc{} || result.ptr != text.data() + text.size()) {
        fail("line " + std::to_string(line_number) + ": invalid decimal u64");
    }
    return value;
}

bool valid_id(const std::string& id) {
    if (id.empty()) {
        return false;
    }
    for (const unsigned char value : id) {
        const bool alpha = (value >= 'A' && value <= 'Z') || (value >= 'a' && value <= 'z');
        const bool digit = value >= '0' && value <= '9';
        if (!alpha && !digit && value != '_' && value != '.' && value != '-') {
            return false;
        }
    }
    return true;
}

std::vector<std::string> split_tabs(const std::string& line) {
    std::vector<std::string> fields;
    std::size_t start = 0;
    while (true) {
        const std::size_t next = line.find('\t', start);
        fields.push_back(line.substr(start, next == std::string::npos ? next : next - start));
        if (next == std::string::npos) {
            break;
        }
        start = next + 1;
    }
    return fields;
}

std::vector<Candidate> read_candidates() {
    std::string line;
    if (!std::getline(std::cin, line)) {
        fail("missing protocol header");
    }
    if (!line.empty() && line.back() == '\r') {
        line.pop_back();
    }
    if (line != "NATIVE_PROXY_V1") {
        fail("first line must be NATIVE_PROXY_V1");
    }

    std::vector<Candidate> candidates;
    std::unordered_set<std::string> seen;
    std::size_t line_number = 1;
    while (std::getline(std::cin, line)) {
        ++line_number;
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        if (line.empty()) {
            continue;
        }
        const auto fields = split_tabs(line);
        if (fields.size() != 8) {
            fail("line " + std::to_string(line_number) + ": expected 8 tab-separated fields");
        }
        if (!valid_id(fields[0])) {
            fail("line " + std::to_string(line_number) + ": invalid candidate_id");
        }
        if (!seen.insert(fields[0]).second) {
            fail("line " + std::to_string(line_number) + ": duplicate candidate_id");
        }
        Candidate candidate{
            fields[0], parse_u64(fields[1], line_number), parse_u64(fields[2], line_number),
            parse_u64(fields[3], line_number), parse_u64(fields[4], line_number),
            parse_u64(fields[5], line_number), parse_u64(fields[6], line_number),
            parse_u64(fields[7], line_number)};
        if (candidate.bandwidth == 0) {
            fail("line " + std::to_string(line_number) + ": bandwidth must be positive");
        }
        if (candidate.cross_core_count > candidate.cross_task_count) {
            fail("line " + std::to_string(line_number) +
                 ": cross_core_count exceeds cross_task_count");
        }
        candidates.push_back(std::move(candidate));
    }
    if (candidates.empty()) {
        fail("input must contain at least one candidate");
    }
    return candidates;
}

Ranked score(const Candidate& candidate) {
    const U64 compute_q6 = std::max(candidate.pipe_bound_q6, candidate.dependency_bound_q6);
    const U64 numerator = checked_mul(candidate.copy_bytes, 1'000'000, "transfer");
    U64 transfer_q6 = numerator / candidate.bandwidth;
    if (numerator % candidate.bandwidth != 0) {
        transfer_q6 = checked_add(transfer_q6, 1, "transfer ceiling");
    }
    const U64 task_penalty = checked_mul(candidate.cross_task_count, 25'000, "task penalty");
    const U64 core_penalty = checked_mul(candidate.cross_core_count, 225'000, "core penalty");
    const U64 communication = checked_add(task_penalty, core_penalty, "communication penalty");
    const U64 imbalance = candidate.imbalance_ppm > 1'000'000
                              ? candidate.imbalance_ppm - 1'000'000
                              : 0;
    U64 total = checked_add(compute_q6, transfer_q6, "score");
    total = checked_add(total, communication, "score");
    total = checked_add(total, imbalance, "score");
    return Ranked{candidate.id, compute_q6, transfer_q6, communication, imbalance, total};
}

}  // namespace

int main() {
#ifdef _WIN32
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    try {
        auto candidates = read_candidates();
        std::vector<Ranked> ranked;
        ranked.reserve(candidates.size());
        for (const auto& candidate : candidates) {
            ranked.push_back(score(candidate));
        }
        std::sort(ranked.begin(), ranked.end(), [](const Ranked& left, const Ranked& right) {
            return left.score_q6 != right.score_q6 ? left.score_q6 < right.score_q6
                                                   : left.id < right.id;
        });
        std::ostringstream output;
        output << "rank\tcandidate_id\tcompute_q6\ttransfer_q6\tcommunication_penalty_q6\t"
                  "imbalance_penalty_q6\tscore_q6\n";
        for (std::size_t index = 0; index < ranked.size(); ++index) {
            const auto& item = ranked[index];
            output << index + 1 << '\t' << item.id << '\t' << item.compute_q6 << '\t'
                   << item.transfer_q6 << '\t' << item.communication_penalty_q6 << '\t'
                   << item.imbalance_penalty_q6 << '\t' << item.score_q6 << '\n';
        }
        std::cout << output.str();
    } catch (const std::exception& error) {
        std::cerr << "protocol error: " << error.what() << '\n';
        return 2;
    }
    return 0;
}
