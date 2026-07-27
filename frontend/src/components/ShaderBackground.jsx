import { useEffect, useRef } from 'react'

const VS = `
attribute vec2 a_position;
varying vec2 v_texCoord;
void main() {
  v_texCoord = a_position * 0.5 + 0.5;
  gl_Position = vec4(a_position, 0.0, 1.0);
}`

const FS = `
precision highp float;
varying vec2 v_texCoord;
uniform float u_time;
uniform vec2 u_resolution;
uniform vec2 u_mouse;
uniform float u_dark;

vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec2 mod289(vec2 v) { return v - floor(v * (1.0 / 289.0)) * 289.0; }
vec3 permute(vec3 x) { return mod289(((x*34.0)+1.0)*x); }

float snoise(vec2 v) {
  const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024390243902439);
  vec2 i  = floor(v + dot(v, C.yy));
  vec2 x0 = v - i + dot(i, C.xx);
  vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
  vec4 x12 = x0.xyxy + C.xxzz;
  x12.xy -= i1;
  i = mod289(i);
  vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0)) + i.x + vec3(0.0, i1.x, 1.0));
  vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
  m = m*m; m = m*m;
  vec3 x2 = 2.0 * fract(p * C.www) - 1.0;
  vec3 h = abs(x2) - 0.5;
  vec3 a0 = x2 - floor(x2 + 0.5);
  vec3 g = a0.x * vec2(x0.x, x12.x) + a0.y * vec2(x0.y, x12.y);
  return 130.0 * dot(m, g);
}

void main() {
  vec2 uv = v_texCoord;
  vec2 mouse = u_mouse / u_resolution;
  vec3 light1 = vec3(0.96, 0.94, 0.91);
  vec3 light2 = vec3(1.0, 0.80, 0.0);
  vec3 dark1  = vec3(0.07, 0.07, 0.07);
  vec3 dark2  = vec3(0.35, 0.28, 0.0);
  vec3 color1 = mix(light1, dark1, u_dark);
  vec3 color2 = mix(light2, dark2, u_dark);
  float noise1 = snoise(uv * 2.0 + u_time * 0.08) * 0.5 + 0.5;
  float noise2 = snoise(uv * 4.0 - u_time * 0.12 + mouse * 2.0) * 0.5 + 0.5;
  float dist = distance(uv, mouse);
  float glow = smoothstep(0.5, 0.0, dist) * 0.15;
  float mixFactor = mix(noise1, noise2, 0.5) * 0.10 + glow;
  vec3 finalColor = mix(color1, color2, mixFactor);
  gl_FragColor = vec4(finalColor, 1.0);
}`

export default function ShaderBackground({ isDark = false }) {
  const canvasRef = useRef(null)
  const darkRef = useRef(isDark ? 1 : 0)

  useEffect(() => {
    darkRef.current = isDark ? 1 : 0
  }, [isDark])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const syncSize = () => {
      const w = canvas.clientWidth || window.innerWidth || 1280
      const h = canvas.clientHeight || window.innerHeight || 720
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w
        canvas.height = h
      }
    }
    const ro = new ResizeObserver(syncSize)
    ro.observe(canvas)
    syncSize()

    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl')
    if (!gl) return

    const compile = (type, src) => {
      const s = gl.createShader(type)
      gl.shaderSource(s, src)
      gl.compileShader(s)
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) return null
      return s
    }

    const vsShader = compile(gl.VERTEX_SHADER, VS)
    const fsShader = compile(gl.FRAGMENT_SHADER, FS)
    if (!vsShader || !fsShader) return

    const prog = gl.createProgram()
    gl.attachShader(prog, vsShader)
    gl.attachShader(prog, fsShader)
    gl.linkProgram(prog)
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return
    gl.useProgram(prog)

    const buf = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, buf)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 1,-1, -1,1, 1,1]), gl.STATIC_DRAW)
    const pos = gl.getAttribLocation(prog, 'a_position')
    if (pos === -1) return
    gl.enableVertexAttribArray(pos)
    gl.vertexAttribPointer(pos, 2, gl.FLOAT, false, 0, 0)

    const uTime  = gl.getUniformLocation(prog, 'u_time')
    const uRes   = gl.getUniformLocation(prog, 'u_resolution')
    const uMouse = gl.getUniformLocation(prog, 'u_mouse')
    const uDark  = gl.getUniformLocation(prog, 'u_dark')

    let mouse = { x: canvas.width / 2, y: canvas.height / 2 }
    const onMouseMove = (e) => {
      const r = canvas.getBoundingClientRect()
      if (r.width && r.height) {
        mouse.x = ((e.clientX - r.left) / r.width) * canvas.width
        mouse.y = (1 - (e.clientY - r.top) / r.height) * canvas.height
      }
    }
    window.addEventListener('mousemove', onMouseMove)

    let raf
    const render = (t) => {
      syncSize()
      gl.viewport(0, 0, canvas.width, canvas.height)
      if (uTime) gl.uniform1f(uTime, t * 0.001)
      if (uRes) gl.uniform2f(uRes, canvas.width, canvas.height)
      if (uMouse) gl.uniform2f(uMouse, mouse.x, mouse.y)
      if (uDark) gl.uniform1f(uDark, darkRef.current)
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4)
      raf = requestAnimationFrame(render)
    }
    raf = requestAnimationFrame(render)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('mousemove', onMouseMove)
      ro.disconnect()
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 w-full h-full -z-10"
      style={{ display: 'block' }}
    />
  )
}
