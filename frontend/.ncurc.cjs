/** @type {import('npm-check-updates').RunOptions} */
module.exports = {
  // Pin package.json to EXACT versions on update (strip ^/~) so the manifest
  // itself is reproducible, not just the lockfile.
  removeRange: true,
  // Skip any version published in the last 10 days — most malicious npm
  // releases are caught within hours.
  cooldown: 10,
};
