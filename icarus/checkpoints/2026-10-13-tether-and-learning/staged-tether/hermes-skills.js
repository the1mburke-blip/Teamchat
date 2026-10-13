import {readFileSync} from 'node:fs';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {join} from 'node:path';

const root=fileURLToPath(new URL('./hermes-skills/',import.meta.url));
const manifest=JSON.parse(readFileSync(join(root,'manifest.json'),'utf8'));
const providerName='icarus-hermes-skills';
const names=new Set();
const candidates=manifest.skills.map(skill=>{
  if(!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(skill.name)||names.has(skill.name)||typeof skill.description!=='string'||!skill.description)throw new Error('Invalid packaged Hermes skill metadata');
  names.add(skill.name);
  return {name:skill.name,description:skill.description,provider:providerName,source:'bundled',rank:600,invocation:{modelInvocable:true,userInvocable:true},resourceBase:{kind:'directory',path:join(root,skill.name)}};
});

// This registers procedures only. Tool dispatch and authority stay with DSH/ICARUS.
export function applyHermesSkills(ctx){
  ctx.skills.registerProvider(()=>({
    name:providerName,
    list:async()=>candidates.map(c=>({...c,invocation:{...c.invocation},resourceBase:{...c.resourceBase}})),
    async get(candidate,options={}){
      const owned=candidates.find(c=>c.name===candidate.name);
      if(!owned)return undefined;
      const raw=await readFile(join(owned.resourceBase.path,'SKILL.md'),{encoding:'utf8',signal:options.signal});
      const frontmatter=/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/u.exec(raw);
      if(!frontmatter)throw new Error(`Packaged Hermes skill ${owned.name} has no frontmatter`);
      const {rank,...summary}=owned;
      return {...summary,invocation:{...owned.invocation},resourceBase:{...owned.resourceBase},content:raw.slice(frontmatter[0].length).trim()};
    }
  }));
}
