/**
 * GreenBin - Encuesta de conocimiento del código de colores y percepción del sistema
 * Crea automáticamente el formulario en Google Forms y una hoja de cálculo para las respuestas.
 *
 * Cómo usarlo:
 *   1. Entre a https://script.google.com con la cuenta de Google que será dueña del formulario.
 *   2. "Nuevo proyecto" → borre el contenido de Código.gs → pegue este archivo completo → guarde.
 *   3. Arriba, en la lista de funciones, elija "crearEncuestaGreenBin" y pulse "Ejecutar".
 *   4. La primera vez Google pide permisos (Forms y Hojas de cálculo): acéptelos.
 *   5. Abra "Registro de ejecución": allí aparecen el enlace para responder, el de edición
 *      y el de la hoja de respuestas. El formulario también queda en su Google Drive.
 *
 * Cada ejecución crea un formulario NUEVO: ejecútelo una sola vez (o borre los de prueba en Drive).
 */

const TITULO = 'Encuesta GreenBin: separación de residuos en la FET';

// Preguntas de "¿en qué caneca va?" (Resolución 2184 de 2019 y criterio del proyecto)
const RESIDUOS = [
  ['Botella plástica de gaseosa o agua, vacía', 'Blanca',
   'Las botellas plásticas son aprovechables: van en la caneca blanca, vacías.'],
  ['Lata de bebida (por ejemplo, Speed o gaseosa)', 'Blanca',
   'Las latas de aluminio son aprovechables: van en la caneca blanca.'],
  ['Servilleta usada', 'Negra',
   'Las servilletas usadas no son aprovechables: van en la caneca negra.'],
  ['Paquete de papas o de mecato (empaque plateado por dentro)', 'Negra',
   'Los empaques metalizados de snacks no se pueden aprovechar: van en la caneca negra.'],
  ['Vaso de cartón para café, ya usado', 'Negra',
   'Los vasos de cartón para bebidas calientes tienen una capa plástica y quedan con residuos de bebida: van en la caneca negra.'],
  ['Cáscara de banano', 'Verde',
   'Las cáscaras y los restos de comida son orgánicos aprovechables: van en la caneca verde.'],
  ['Vaso plástico desechable, ya usado', 'Negra',
   'Los vasos desechables usados quedan con residuos de bebida: van en la caneca negra.'],
  ['Papel de envolver hamburguesa, con grasa', 'Negra',
   'El papel con grasa o restos de comida no se puede aprovechar: va en la caneca negra.'],
];
const CANECAS = ['Blanca', 'Negra', 'Verde', 'No sé'];

function crearEncuestaGreenBin() {
  const form = FormApp.create(TITULO);
  form.setDescription(
    'Somos estudiantes de Ingeniería de Software de la Fundación Escuela Tecnológica de Neiva (FET) ' +
    'y desarrollamos GreenBin, un prototipo que orienta la separación de residuos en la fuente.\n\n' +
    'Esta encuesta busca conocer qué tanto se conoce el código de colores para la separación de residuos ' +
    '(Resolución 2184 de 2019) y qué opina la comunidad sobre el sistema. Toma unos 5 minutos.\n\n' +
    'La participación es voluntaria y anónima: no se pide nombre, correo, documento ni ningún dato que lo identifique. ' +
    'Las respuestas se usarán solo con fines académicos y se analizarán de forma agregada, conforme a la Ley 1581 de 2012. ' +
    'Al final verá las respuestas correctas, para que la encuesta también sirva como guía.');
  form.setIsQuiz(true);
  form.setCollectEmail(false);
  form.setProgressBar(true);
  form.setAllowResponseEdits(false);
  form.setShowLinkToRespondAgain(false);
  form.setPublishingSummary(false);
  form.setConfirmationMessage('¡Gracias por participar! Recuerde: blanca para aprovechables limpios, ' +
    'negra para no aprovechables y verde para orgánicos.');

  // ── Página 1: consentimiento ──
  const consentimiento = form.addMultipleChoiceItem()
    .setTitle('¿Acepta participar voluntariamente en esta encuesta?')
    .setRequired(true);
  consentimiento.setChoices([
    consentimiento.createChoice('Sí, acepto participar', FormApp.PageNavigationType.CONTINUE),
    consentimiento.createChoice('No acepto', FormApp.PageNavigationType.SUBMIT),
  ]);

  // ── Página 2: perfil ──
  form.addPageBreakItem().setTitle('Sobre usted');
  opcion(form, 'Usted es:', ['Estudiante', 'Docente', 'Administrativo', 'Personal de servicios generales o cafetería', 'Otro']);
  opcion(form, '¿Con qué frecuencia deposita residuos en los puntos ecológicos de la FET?',
    ['Nunca', 'Rara vez', 'A veces', 'Casi siempre', 'Siempre']);
  opcion(form, '¿Conoce el código de colores para separar residuos en canecas blanca, negra y verde?',
    ['Sí, lo conozco bien', 'Lo conozco parcialmente', 'No lo conozco']);

  // ── Página 3: conocimiento (preguntas calificadas) ──
  form.addPageBreakItem()
    .setTitle('¿En qué caneca va?')
    .setHelpText('Indique en qué caneca debe depositarse cada residuo. Si no lo sabe, elija "No sé": ' +
      'nos interesa saber qué tan claro es el código de colores, no que acierte.');
  RESIDUOS.forEach(function ([residuo, correcta, explicacion]) {
    const item = form.addMultipleChoiceItem().setTitle(residuo).setRequired(true).setPoints(1);
    item.setChoices(CANECAS.map(function (c) { return item.createChoice(c, c === correcta); }));
    const fb = FormApp.createFeedback().setText(explicacion).build();
    item.setFeedbackForCorrect(fb);
    item.setFeedbackForIncorrect(fb);
  });

  // ── Página 4: hábitos ──
  form.addPageBreakItem().setTitle('Sus hábitos');
  opcion(form, 'Cuando no está seguro de en qué caneca va un residuo, ¿qué hace normalmente?',
    ['Lo deposito en cualquier caneca', 'Lo deposito en la que creo más probable',
     'Busco la señalización del punto ecológico', 'Le pregunto a alguien'], true);
  form.addScaleItem()
    .setTitle('¿Qué tan clara le parece la señalización de los puntos ecológicos de la FET?')
    .setBounds(1, 5).setLabels('Nada clara', 'Muy clara').setRequired(true);

  // ── Página 5: GreenBin ──
  form.addPageBreakItem()
    .setTitle('Sobre GreenBin')
    .setHelpText('GreenBin es un prototipo que, al acercar un residuo, lo reconoce con una cámara y ' +
      'le indica por voz en qué caneca depositarlo. No graba video ni envía imágenes: solo guarda en el ' +
      'equipo, con los rostros pixelados, las fotos de los residuos que no logra reconocer, para mejorar el sistema.');
  opcion(form, '¿Ha visto o usado GreenBin en la FET?', ['Sí, lo usé', 'Lo vi, pero no lo usé', 'No']);
  form.addScaleItem()
    .setTitle('¿Qué tan útil le parece un sistema que le indique por voz en qué caneca depositar cada residuo?')
    .setBounds(1, 5).setLabels('Nada útil', 'Muy útil').setRequired(true);
  opcion(form, 'Si lo usó, ¿la indicación por voz fue clara?',
    ['Sí', 'Más o menos', 'No', 'No lo he usado']);
  opcion(form, '¿Usaría GreenBin si estuviera instalado en los puntos ecológicos?', ['Sí', 'Tal vez', 'No']);
  opcion(form, '¿Le genera alguna preocupación que el sistema use una cámara?',
    ['No', 'Un poco', 'Sí, bastante']);
  form.addParagraphTextItem()
    .setTitle('Comentarios o sugerencias para mejorar GreenBin (opcional)')
    .setRequired(false);

  // ── Hoja de respuestas ──
  const hoja = SpreadsheetApp.create(TITULO + ' (respuestas)');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, hoja.getId());

  Logger.log('Enlace para responder (compártalo): ' + form.getPublishedUrl());
  Logger.log('Enlace para editar el formulario:   ' + form.getEditUrl());
  Logger.log('Hoja con las respuestas:            ' + hoja.getUrl());
}

/** Pregunta de opción única, obligatoria. Con otra=true agrega la opción "Otro". */
function opcion(form, titulo, opciones, otra) {
  const item = form.addMultipleChoiceItem().setTitle(titulo).setChoiceValues(opciones).setRequired(true);
  if (otra) item.showOtherOption(true);
  return item;
}
