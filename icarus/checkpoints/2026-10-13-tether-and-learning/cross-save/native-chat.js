// Safe text history adapter. Runtime approval, model, system, sandbox, scheduling
// and tool-execution events are deliberately outside this first adapter.
export function portableChat(events,{workspaceId,title}){
 const messages=[];
 for(const event of events){
  if(!['user/message','assistant/message'].includes(event.type))continue;
  if(event.type==='user/message'&&event.data?.source?.kind!=='user')continue;
  const role=event.type==='user/message'?'user':'assistant';
  const content=(event.data?.content??[]).filter(part=>part.type==='text').map(part=>part.text).join('\n');
  if(content)messages.push({role,content});
 }
 return {workspaceId,title,messages};
}
export function restoredChatEvents(chat,{createUserMessage,createAssistantMessage}){
 return chat.messages.map((message,seq)=>({seq,time:Date.now(),type:message.role+'/message',data:(message.role==='user'?createUserMessage:createAssistantMessage)({content:[{type:'text',text:message.content}],source:message.role==='user'?{kind:'user'}:{kind:'model',provider:'cross-save-history',model:'recorded-history'}})}));
}
export function prepareNativeChat(ctx,chat,{id,cwd,createUserMessage,createAssistantMessage}){
 // Prepare only: no publication, persistence, active-agent interruption or model call.
 return ctx.sessions.prepare(id,{seed:restoredChatEvents(chat,{createUserMessage,createAssistantMessage}),meta:{cwd,isSeeded:true,delegationDepth:0}});
}
