import { useState } from "react";
import { domAnimation, LazyMotion } from "motion/react";
import * as m from "motion/react-m";
import Marca from "../../nucleo/componentes/Marca";

const transicion = { delay: 0.25, duration: 1.85, ease: [0.65, 0, 0.35, 1] as const };

export default function CortinaLogin() {
  const [termino, setTermino] = useState(false);
  if (termino) return null;

  return (
    <LazyMotion features={domAnimation}>
      <div className="login-cortina" aria-hidden="true">
        <m.div
          className="login-cortina-mitad login-cortina-superior"
          initial={{ x: 0, y: 0 }}
          animate={{ x: "-100%", y: "-100%" }}
          transition={transicion}
        >
          <Marca />
        </m.div>
        <m.div
          className="login-cortina-mitad login-cortina-inferior"
          initial={{ x: 0, y: 0 }}
          animate={{ x: "100%", y: "100%" }}
          transition={transicion}
          onAnimationComplete={() => setTermino(true)}
        >
          <Marca />
        </m.div>
      </div>
    </LazyMotion>
  );
}
