import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
const skills=JSON.parse(readFileSync(new URL('../hermes-skills/manifest.json',import.meta.url),'utf8'));
export const runtimePluginFiles=['index.js','client.js','model-selector.js','quota-state.js','hermes-skills.js','icarus-learning.js','hermes-skills/manifest.json',...skills.runtimeFiles,'cordis.patch.yml','package.json','AGENTS.md','identity.md','inherited.md','learned.md','current-state.md'];
export function runtimeManifest(root,pkg) {
  const hash=createHash('sha256');
  for(const name of runtimePluginFiles)hash.update(name+'\0').update(readFileSync(join(root,name))).update('\0');
  return JSON.stringify({node:pkg.dsh.androidRuntime.node,dsh:pkg.dsh.androidRuntime.dsh,app:pkg.version,pluginSourceSha256:hash.digest('hex')},null,2)+'\n';
}
