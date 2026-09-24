use std::collections::HashSet;
use std::io::{self, Read, Write};

#[derive(Debug)]
struct Candidate {
    id: String,
    pipe_bound_q6: u64,
    dependency_bound_q6: u64,
    copy_bytes: u64,
    bandwidth: u64,
    cross_task_count: u64,
    cross_core_count: u64,
    imbalance_ppm: u64,
}
#[derive(Debug)]
struct Ranked {
    id: String,
    compute_q6: u64,
    transfer_q6: u64,
    communication_penalty_q6: u64,
    imbalance_penalty_q6: u64,
    score_q6: u64,
}

fn checked_add(left: u64, right: u64, label: &str) -> Result<u64, String> {
    left.checked_add(right)
        .ok_or_else(|| format!("overflow while computing {label}"))
}

fn checked_mul(left: u64, right: u64, label: &str) -> Result<u64, String> {
    left.checked_mul(right)
        .ok_or_else(|| format!("overflow while computing {label}"))
}

fn valid_id(id: &str) -> bool {
    !id.is_empty()
        && id
            .bytes()
            .all(|value| value.is_ascii_alphanumeric() || matches!(value, b'_' | b'.' | b'-'))
}

fn parse_u64(text: &str, line_number: usize) -> Result<u64, String> {
    if text.is_empty() || !text.bytes().all(|value| value.is_ascii_digit()) {
        return Err(format!("line {line_number}: invalid decimal u64"));
    }
    text.parse::<u64>()
        .map_err(|_| format!("line {line_number}: decimal value exceeds u64"))
}

fn parse_input(raw: &[u8]) -> Result<Vec<Candidate>, String> {
    if !raw.is_ascii() {
        return Err("input must be ASCII".to_string());
    }
    let text = std::str::from_utf8(raw).map_err(|_| "input must be ASCII".to_string())?;
    let mut lines = text.lines();
    if lines.next() != Some("NATIVE_PROXY_V1") {
        return Err("first line must be NATIVE_PROXY_V1".to_string());
    }
    let mut candidates = Vec::new();
    let mut seen = HashSet::new();
    for (offset, line) in lines.enumerate() {
        let line_number = offset + 2;
        if line.is_empty() {
            continue;
        }
        let fields: Vec<&str> = line.split('\t').collect();
        if fields.len() != 8 {
            return Err(format!(
                "line {line_number}: expected 8 tab-separated fields"
            ));
        }
        if !valid_id(fields[0]) {
            return Err(format!("line {line_number}: invalid candidate_id"));
        }
        if !seen.insert(fields[0].to_string()) {
            return Err(format!("line {line_number}: duplicate candidate_id"));
        }
        let candidate = Candidate {
            id: fields[0].to_string(),
            pipe_bound_q6: parse_u64(fields[1], line_number)?,
            dependency_bound_q6: parse_u64(fields[2], line_number)?,
            copy_bytes: parse_u64(fields[3], line_number)?,
            bandwidth: parse_u64(fields[4], line_number)?,
            cross_task_count: parse_u64(fields[5], line_number)?,
            cross_core_count: parse_u64(fields[6], line_number)?,
            imbalance_ppm: parse_u64(fields[7], line_number)?,
        };
        if candidate.bandwidth == 0 {
            return Err(format!("line {line_number}: bandwidth must be positive"));
        }
        if candidate.cross_core_count > candidate.cross_task_count {
            return Err(format!(
                "line {line_number}: cross_core_count exceeds cross_task_count"
            ));
        }
        candidates.push(candidate);
    }
    if candidates.is_empty() {
        return Err("input must contain at least one candidate".to_string());
    }
    Ok(candidates)
}

fn score(candidate: Candidate) -> Result<Ranked, String> {
    let compute_q6 = candidate.pipe_bound_q6.max(candidate.dependency_bound_q6);
    let numerator = checked_mul(candidate.copy_bytes, 1_000_000, "transfer")?;
    let mut transfer_q6 = numerator / candidate.bandwidth;
    if numerator % candidate.bandwidth != 0 {
        transfer_q6 = checked_add(transfer_q6, 1, "transfer ceiling")?;
    }
    let task_penalty = checked_mul(candidate.cross_task_count, 25_000, "task penalty")?;
    let core_penalty = checked_mul(candidate.cross_core_count, 225_000, "core penalty")?;
    let communication_penalty_q6 =
        checked_add(task_penalty, core_penalty, "communication penalty")?;
    let imbalance_penalty_q6 = candidate.imbalance_ppm.saturating_sub(1_000_000);
    let mut score_q6 = checked_add(compute_q6, transfer_q6, "score")?;
    score_q6 = checked_add(score_q6, communication_penalty_q6, "score")?;
    score_q6 = checked_add(score_q6, imbalance_penalty_q6, "score")?;
    Ok(Ranked {
        id: candidate.id,
        compute_q6,
        transfer_q6,
        communication_penalty_q6,
        imbalance_penalty_q6,
        score_q6,
    })
}

fn run() -> Result<(), String> {
    let mut raw = Vec::new();
    io::stdin()
        .read_to_end(&mut raw)
        .map_err(|error| format!("cannot read stdin: {error}"))?;
    let mut ranked: Vec<Ranked> = parse_input(&raw)?
        .into_iter()
        .map(score)
        .collect::<Result<Vec<_>, _>>()?;
    ranked.sort_by(|left, right| {
        left.score_q6
            .cmp(&right.score_q6)
            .then_with(|| left.id.cmp(&right.id))
    });

    let stdout = io::stdout();
    let mut output = io::BufWriter::new(stdout.lock());
    output
        .write_all(b"rank\tcandidate_id\tcompute_q6\ttransfer_q6\tcommunication_penalty_q6\timbalance_penalty_q6\tscore_q6\n")
        .map_err(|error| format!("cannot write stdout: {error}"))?;
    for (index, item) in ranked.iter().enumerate() {
        writeln!(
            output,
            "{}\t{}\t{}\t{}\t{}\t{}\t{}",
            index + 1,
            item.id,
            item.compute_q6,
            item.transfer_q6,
            item.communication_penalty_q6,
            item.imbalance_penalty_q6,
            item.score_q6
        )
        .map_err(|error| format!("cannot write stdout: {error}"))?;
    }
    output
        .flush()
        .map_err(|error| format!("cannot flush stdout: {error}"))?;
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("protocol error: {error}");
        std::process::exit(2);
    }
}
