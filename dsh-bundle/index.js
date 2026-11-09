/**
 * filmcraft-studio — DeepSeek Harness Host plugin.
 *
 * Registers one tool, `filmcraft_montage`, that runs the FilmCraft creative
 * engine (../filmcraft_studio.py, next to this bundle) on a workspace folder and
 * returns the saved project, the exported video, and the verification result.
 *
 * The engine does the real work through bridge.py -> filmcraft-cli; this module
 * is only the Harness-facing adapter (schema, working-directory default, spawn,
 * error surface).
 */

import { execFile } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { promisify } from 'node:util'

const run = promisify(execFile)

const PACKAGE_DIR = path.dirname(fileURLToPath(import.meta.url))
const ENGINE = path.resolve(PACKAGE_DIR, '..', 'filmcraft_studio.py')

const PARAMETERS = {
  type: 'object',
  properties: {
    workspace: {
      type: 'string',
      description:
        'Absolute path of the folder to edit. Omit to use the current session working directory.',
    },
    brief: {
      type: 'string',
      description: 'The user request in natural language; it selects the theme and the copy.',
    },
    media: {
      type: 'array',
      items: { type: 'string' },
      description: 'Explicit video files. Omitted: every video found in the workspace.',
    },
    language: { type: 'string', enum: ['ar', 'en'], description: 'Design language. Default ar.' },
    theme: {
      type: 'string',
      enum: ['auto', 'security', 'generic'],
      description: 'Graphic theme. auto reads the brief and the transcript.',
    },
    captions: { type: 'boolean', description: 'Burn captions from the local speech transcript.' },
    tighten: {
      type: 'number',
      description: 'Remove speech pauses longer than this many seconds before designing.',
    },
    name: { type: 'string', description: 'Project/output base name. Default filmcraft_edit.' },
    export: { type: 'boolean', description: 'Export the MP4 (default true).' },
    noTranscribe: { type: 'boolean', description: 'Skip local speech-to-text for speed.' },
  },
  required: [],
}

const OUTPUT = {
  schema: {
    type: 'object',
    properties: {
      ok: { type: 'boolean' },
      workspace: { type: 'string' },
      project: { type: 'string' },
      output: { type: 'string' },
      verified: { type: 'boolean' },
      seconds: { type: 'number' },
      log: { type: 'string' },
    },
    required: ['ok'],
  },
  render: (_args, value) => [{ type: 'text', text: value.log || JSON.stringify(value) }],
}

const DESCRIPTION =
  'Edit the videos in a folder with FilmCraft: analyse them, build a saved .fcproj ' +
  '(Arabic/English titles, lower third, end card, colour grade, push-in, audio fades), ' +
  'optionally transcribe the speech locally and burn captions, export an MP4 and verify ' +
  'the exported file. Call it with the workspace path (or omit it to use the current folder). ' +
  'It is slow (minutes) and writes into the workspace: <name>.fcproj, out/<name>.mp4, renders/.'

export const inject = ['tools']

export function apply(ctx) {
  ctx.tools.register({
    name: 'filmcraft_montage',
    description: DESCRIPTION,
    parameters: PARAMETERS,
    output: OUTPUT,
    timeoutMs: 1_800_000,
    presentCall: (args) => ({
      card: 'generic',
      title: 'FilmCraft montage',
      kind: 'execute',
      rawInput: args,
    }),
    async execute(args, exec) {
      let workspace = args.workspace
      if (!workspace) {
        const session = exec.agent && exec.agent.session
        const workingDirectory = ctx.get('workingDirectory')
        if (session && workingDirectory) workspace = workingDirectory.get(session)
      }
      if (!workspace) {
        throw new Error('filmcraft_montage needs `workspace` (no session working directory found)')
      }

      const argv = [ENGINE, '--workspace', workspace]
      if (args.brief) argv.push('--brief', String(args.brief))
      if (args.media && args.media.length) argv.push('--media', ...args.media.map(String))
      if (args.language) argv.push('--language', String(args.language))
      if (args.theme) argv.push('--theme', String(args.theme))
      if (args.captions) argv.push('--captions')
      if (typeof args.tighten === 'number' && args.tighten > 0) argv.push('--tighten', String(args.tighten))
      if (args.name) argv.push('--name', String(args.name))
      if (args.export === false) argv.push('--no-export')
      if (args.noTranscribe) argv.push('--no-transcribe')

      const started = Date.now()
      let stdout = ''
      let stderr = ''
      try {
        const result = await run('python', argv, {
          cwd: workspace,
          timeout: 1_700_000,
          maxBuffer: 64 * 1024 * 1024,
          windowsHide: true,
        })
        stdout = result.stdout || ''
        stderr = result.stderr || ''
      } catch (error) {
        stdout = (error && error.stdout) || ''
        stderr = (error && error.stderr) || ''
        const tail = (stdout + '\n' + stderr).trim().slice(-4000)
        throw new Error(`filmcraft_montage failed: ${(error && error.message) || error}\n${tail}`)
      }

      const tail = stdout.trim().split(/\r?\n/).slice(-24).join('\n')
      const done = /DONE project=(.+?) output=(.+?) verified=(\w+)/.exec(stdout)
      const doneNoExport = /DONE \(no export\) project=(.+)/.exec(stdout)
      return {
        ok: true,
        workspace,
        project: done ? done[1] : doneNoExport ? doneNoExport[1] : '',
        output: done ? done[2] : '',
        verified: done ? done[3] === 'True' : false,
        seconds: Math.round((Date.now() - started) / 100) / 10,
        log: tail,
      }
    },
  })
}
