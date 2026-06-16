import type { ExtensionAPI } from '@earendil-works/pi-coding-agent';

export interface GitExecResult {
  code: number;
  stdout: string;
}

/**
 * Run a git command inside `cwd` via the pi exec API.
 * Returns null on any execution error rather than throwing.
 */
export const execGit = async (
  pi: ExtensionAPI,
  cwd: string,
  args: string[],
): Promise<GitExecResult | null> => {
  try {
    return (await pi.exec('git', ['-C', cwd, ...args], {
      timeout: 3000,
    })) as GitExecResult;
  } catch {
    return null;
  }
};
