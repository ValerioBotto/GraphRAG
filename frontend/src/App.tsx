import React, { useState, useEffect, useRef } from 'react';
import type { Message, UserData } from './types';
import { AppStep } from './types';
import { IconFileUp, IconSend, IconBot, IconGear, IconSparkles, IconArrowRight, IconLayers, IconDatabase, IconWorkflow, IconGlobe } from './components/Icons';
import ReactMarkdown from 'react-markdown';

const App: React.FC = () => {
  const [step, setStep] = useState<AppStep>(AppStep.NAME_INPUT);
  const [previousStep, setPreviousStep] = useState<AppStep | null>(null);
  const [userData, setUserData] = useState<UserData>({ name: '' });
  const [progress, setProgress] = useState(0);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [showPlusMenu, setShowPlusMenu] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const handleNameSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (userData.name.trim()) {
      setStep(AppStep.PDF_UPLOAD);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUserData({ ...userData, fileName: file.name });
      setStep(AppStep.PROCESSING);
      setProgress(10); 

      const formData = new FormData();
      formData.append('file', file);
      formData.append('user_id', userData.name);

      // Incremento simulato della barra per dare feedback visuale durante l'elaborazione pesante
      const progressInterval = setInterval(() => {
        setProgress(prev => (prev < 90 ? prev + 5 : prev));
      }, 800);

      try {
        const response = await fetch('http://127.0.0.1:8000/upload', {
          method: 'POST',
          body: formData,
        });

        clearInterval(progressInterval);

        if (response.ok) {
          setProgress(100);
          setTimeout(() => {
            setStep(AppStep.CHAT);
            setMessages([{ 
              role: 'ai', 
              content: 'PRESET_WELCOME', 
              timestamp: new Date() 
            }]);
          }, 600);
        } else {
          throw new Error("Errore durante l'elaborazione del server");
        }
      } catch (error) {
        clearInterval(progressInterval);
        console.error("Errore durante l'ingestione:", error);
        alert("Errore nel caricamento del file. Assicurati che il backend sia attivo e Neo4j sia raggiungibile.");
        setStep(AppStep.PDF_UPLOAD);
      }
    }
  };

  const truncateFileName = (name: string, limit = 25) => {
    if (name.length <= limit) return name;
    return name.substring(0, limit) + '...';
  };

  const handleHomeClick = () => {
    setStep(AppStep.NAME_INPUT);
    setUserData({ name: '' });
    setMessages([]);
    setProgress(0);
  };

  const handleHowItWorksClick = () => {
    setPreviousStep(step);
    setStep(AppStep.HOW_IT_WORKS);
  };

  const returnFromHowItWorks = () => {
    if (previousStep) {
      setStep(previousStep);
    } else {
      setStep(AppStep.NAME_INPUT);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isTyping) return;

    const userMsg: Message = {
      role: 'user',
      content: inputValue,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMsg]);
    setInputValue('');
    setIsTyping(true);

    try {
      const queryParams = new URLSearchParams({
        query: inputValue,
        filename: userData.fileName || "documento",
        user_id: userData.name
      });

      const response = await fetch(`http://127.0.0.1:8000/chat?${queryParams}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (!response.ok) throw new Error('Errore nella risposta del server');

      const data = await response.json();

      setMessages(prev => [...prev, {
        role: 'ai',
        content: data.answer,
        timestamp: new Date()
      }]);
    } catch (error) {
      console.error("Errore chat:", error);
      setMessages(prev => [...prev, {
        role: 'ai',
        content: "Scusa, si è verificato un errore nel collegamento con il server. Assicurati che il backend sia attivo.",
        timestamp: new Date()
      }]);
    } finally {
      setIsTyping(false);
    }
  };

  const isInitialPage = step === AppStep.NAME_INPUT || step === AppStep.PDF_UPLOAD || step === AppStep.PROCESSING;

  return (
    <div className="min-h-screen w-screen flex flex-col font-outfit bg-white overflow-x-hidden">
      
      {/* Header */}
      <header className={`glass-header fixed top-0 w-full z-50 py-3 md:py-4 px-4 md:px-12 flex justify-between items-center transition-opacity ${step === AppStep.CHAT || step === AppStep.HOW_IT_WORKS ? 'opacity-30 hover:opacity-100' : 'opacity-100'}`}>
        <div 
          onClick={handleHomeClick}
          className="flex items-center gap-2 cursor-pointer group"
        >
          <div className="bg-[#FF6600] text-white p-1.5 md:p-2 rounded-lg group-hover:scale-105 transition-transform flex items-center justify-center">
            <IconBot className="w-6 h-6 md:w-8 h-8" />
          </div>
          <span className="text-xl md:text-2xl font-extrabold tracking-tighter transition-colors group-hover:text-[#FF6600]">RAG Chatbot</span>
        </div>
        <div>
          <button 
            onClick={handleHowItWorksClick}
            className="group bg-[#FF6600] text-white w-10 h-10 md:w-auto md:px-4 md:py-2 rounded-lg font-bold text-sm hover:bg-black transition-all active:scale-95 shadow-lg shadow-[#FF6600]/20 flex items-center justify-center"
          >
            <span className="md:hidden text-black font-black text-lg group-hover:text-white transition-colors">?</span>
            <span className="hidden md:inline">Come funziona</span>
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className={`flex-grow flex flex-col items-center ${(step === AppStep.CHAT || step === AppStep.HOW_IT_WORKS) ? 'h-screen pt-20' : 'pt-28 md:pt-32'}`}>
        
        <div className={`w-full ${(step === AppStep.CHAT || step === AppStep.HOW_IT_WORKS) ? 'h-full flex flex-col' : 'max-w-4xl'}`}>
          
          {/* INITIAL STEPS (NAME & UPLOAD) */}
          {(step === AppStep.NAME_INPUT || step === AppStep.PDF_UPLOAD) && (
            <div className="text-center mb-10 md:mb-12 animate-in fade-in slide-in-from-bottom-4 duration-700 px-6">
              <h1 className="text-4xl md:text-6xl font-black mb-4 leading-tight">
                Il Tuo Assistente PDF <br/> 
                <span className="text-[#FF6600]">Intelligente</span>
              </h1>
              <h2 className="text-base md:text-xl text-gray-600 font-light max-w-2xl mx-auto mb-10">
                Carica il tuo PDF e lascialo analizzare dal nostro sistema: Poni domande in chat in linguaggio naturale e ottieni risposte mirate basate esclusivamente sul contenuto del file.
              </h2>

              <div className="flex flex-row items-center justify-center gap-2 md:gap-8 mb-12">
                <div className="flex flex-col items-center gap-3 w-20 md:w-32 group cursor-default">
                  <div className={`w-12 h-12 md:w-16 md:h-16 rounded-full border-2 flex items-center justify-center transition-all bg-gray-50 border-gray-100 text-gray-400 group-hover:text-[#FF6600] group-hover:border-[#FF6600]/30 group-hover:bg-[#FF6600]/5`}>
                    <IconFileUp className="w-5 h-5 md:w-7 md:h-7" />
                  </div>
                  <p className={`text-[8px] md:text-[10px] font-bold tracking-widest uppercase transition-colors text-gray-400 group-hover:text-[#FF6600]`}>1. Upload</p>
                </div>
                <div><IconArrowRight className="text-gray-200 w-3 h-3 md:w-5 md:h-5 animate-pulse" /></div>
                <div className="flex flex-col items-center gap-3 w-20 md:w-32 group cursor-default">
                  <div className="w-12 h-12 md:w-16 md:h-16 rounded-full bg-gray-50 border-2 border-gray-100 flex items-center justify-center text-gray-400 group-hover:text-[#FF6600] group-hover:border-[#FF6600]/30 group-hover:bg-[#FF6600]/5 transition-all">
                    <div className="relative">
                       <IconGear className="w-5 h-5 md:w-7 md:h-7 animate-gear-rotate" />
                       <span className="absolute -top-1 -right-1 bg-[#FF6600] text-white text-[6px] md:text-[8px] font-bold px-1 rounded-sm">PDF</span>
                    </div>
                  </div>
                  <p className="text-[8px] md:text-[10px] font-bold tracking-widest uppercase text-gray-400 group-hover:text-[#FF6600] transition-colors">2. Analisi</p>
                </div>
                <div><IconArrowRight className="text-gray-200 w-3 h-3 md:w-5 md:h-5 animate-pulse" /></div>
                <div className="flex flex-col items-center gap-3 w-20 md:w-32 group cursor-default">
                  <div className="w-12 h-12 md:w-16 md:h-16 rounded-full bg-gray-50 border-2 border-gray-100 flex items-center justify-center text-gray-400 shadow-sm group-hover:text-[#FF6600] group-hover:border-[#FF6600]/30 group-hover:bg-[#FF6600]/5 transition-all">
                    <IconSparkles className="w-5 h-5 md:w-7 md:h-7" />
                  </div>
                  <p className="text-[8px] md:text-[10px] font-bold tracking-widest uppercase text-gray-400 group-hover:text-[#FF6600] transition-colors">3. Chat</p>
                </div>
              </div>
            </div>
          )}

          {step === AppStep.NAME_INPUT && (
            <div className="flex justify-center py-2 animate-in fade-in slide-in-from-top-4 duration-500 px-6">
              <div className="bg-white border border-black/5 p-8 md:p-10 rounded-[2.5rem] shadow-2xl max-w-md w-full orange-glow transition-all">
                <form onSubmit={handleNameSubmit} className="flex flex-col gap-6 md:gap-8">
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-[0.2em] text-gray-400 mb-4 ml-2">Inserisci il tuo nome o User ID</label>
                    <input 
                      type="text" 
                      value={userData.name}
                      onChange={(e) => setUserData({...userData, name: e.target.value})}
                      placeholder="Es: Laura"
                      className="w-full bg-gray-50 border-2 border-transparent focus:border-[#FF6600]/30 focus:bg-white outline-none px-6 md:px-8 py-4 md:py-5 rounded-[1.5rem] text-lg md:text-xl font-semibold text-black placeholder:text-gray-300 transition-all shadow-sm"
                      autoFocus
                    />
                  </div>
                  <button type="submit" disabled={!userData.name.trim()} className="bg-[#FF6600] text-white font-bold py-4 md:py-5 rounded-[1.5rem] hover:bg-black shadow-lg shadow-[#FF6600]/20 transition-all transform active:scale-95 disabled:opacity-30">Continua</button>
                </form>
              </div>
            </div>
          )}

          {step === AppStep.PDF_UPLOAD && (
            <div className="flex flex-col items-center py-2 animate-in fade-in slide-in-from-bottom-8 duration-700 px-6">
              <div className="text-center mb-8">
                <h3 className="text-2xl md:text-3xl font-black text-black mb-2 tracking-tighter uppercase font-outfit">Ciao <span className="text-[#FF6600]">{userData.name}</span></h3>
                <p className="text-gray-400 font-medium">Siamo pronti ad analizzare il tuo file.</p>
              </div>
              <div className="bg-white border-2 border-dashed border-gray-200 p-8 md:p-12 rounded-[3rem] max-w-2xl w-full flex flex-col items-center justify-center gap-6 hover:border-[#FF6600] group transition-all cursor-pointer relative shadow-sm">
                <input type="file" accept="application/pdf" onChange={handleFileUpload} className="absolute inset-0 opacity-0 cursor-pointer" />
                <div className="bg-gray-50 p-4 md:p-6 rounded-full group-hover:bg-[#FF6600]/10 transition-colors">
                  <IconFileUp className="w-10 h-10 md:w-12 md:h-12 text-gray-300 group-hover:text-[#FF6600]" />
                </div>
                <div className="text-center">
                  <p className="text-lg md:text-xl font-bold mb-1">Carica il documento ed inizia a chattare</p>
                  <p className="text-gray-400 text-sm font-medium">Trascina qui il file o clicca per sfogliare</p>
                </div>
              </div>
            </div>
          )}

          {step === AppStep.PROCESSING && (
            <div className="flex-grow flex flex-col items-center justify-center py-16 gap-8 animate-in fade-in px-6">
              <div className="relative w-20 h-20 md:w-24 md:h-24">
                <div className="absolute inset-0 border-4 border-gray-50 rounded-full"></div>
                <div className="absolute inset-0 border-4 border-t-[#FF6600] rounded-full animate-spin"></div>
              </div>
              <div className="text-center max-md:max-w-xs max-w-md">
                <h3 className="text-xl md:text-2xl font-extrabold mb-2">Stiamo processando il tuo documento...</h3>
                <p className="text-gray-500 mb-8 font-light">Quasi pronto...</p>
                <div className="w-full bg-gray-50 h-2 rounded-full overflow-hidden">
                  <div className="bg-[#FF6600] h-full transition-all duration-300" style={{ width: `${progress}%` }}></div>
                </div>
              </div>
            </div>
          )}

          {/* CHAT STEP */}
          {step === AppStep.CHAT && (
            <div className="flex-grow flex flex-col w-full max-w-3xl mx-auto h-full overflow-hidden">
              <div className="flex-grow overflow-y-auto px-6 py-10 space-y-12 chat-scroll">
                {messages.map((msg, idx) => {
                  if (msg.content === 'PRESET_WELCOME') {
                    return (
                      <div key={idx} className="animate-in slide-in-from-bottom-4 duration-700">
                        <div className="flex items-start gap-5">
                           <div className="w-12 h-12 rounded-2xl bg-[#FF6600] flex items-center justify-center shadow-lg shadow-[#FF6600]/20 flex-shrink-0">
                             <div className="relative flex items-center justify-center w-full h-full">
                               <IconBot className="w-9 h-9" />
                               <div className="absolute -top-1 -right-1 bg-white text-black text-[7px] font-black px-1 rounded-sm border border-black/5 uppercase">PDF</div>
                             </div>
                           </div>
                           <div className="flex flex-col gap-1 pt-1">
                            <h2 className="text-xl font-normal text-gray-500 font-verdana leading-tight">
                              <span className="text-[#FF6600] font-medium">{userData.name}</span>, il file{" "}
                              <span className="text-black font-medium hover:text-[#FF6600] cursor-pointer transition-colors" title={userData.fileName}>
                                "{truncateFileName(userData.fileName || '', 40)}" 
                              </span>{" "}
                              è pronto.
                            </h2>
                            <p className="text-sm font-light text-gray-400">
                              Chiedimi qualunque cosa!
                            </p>
                          </div>
                        </div>
                      </div>
                    );
                  }

                  const isUser = msg.role === 'user';
                  return (
                    <div 
                      key={idx} 
                      className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-in fade-in duration-300`}
                    >
                      <div className={`flex gap-4 max-w-[85%] ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
                        {!isUser && (
                          <div className="w-10 h-10 rounded-lg bg-gray-50 flex items-center justify-center flex-shrink-0 mt-1">
                            <IconBot className="w-7 h-7" />
                          </div>
                        )}
                        <div className={`p-4 ${
                          isUser 
                          ? 'bg-gray-100 text-gray-800 rounded-2xl rounded-tr-none' 
                          : 'text-gray-700 leading-relaxed text-[15px] markdown-container'
                        }`}>
                          {/* Rendering Markdown per interpretare il grassetto e altre formattazioni */}
                          <div className="font-verdana">
                            <ReactMarkdown>
                              {msg.content}
                            </ReactMarkdown>
                          </div>
                          <p className="text-[9px] mt-2 opacity-30 font-bold tracking-tighter">
                            {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </p>
                        </div>
                      </div>
                    </div>
                  );
                })}
                {isTyping && (
                  <div className="flex justify-start animate-in fade-in">
                    <div className="flex gap-4">
                      <div className="w-10 h-10 rounded-lg bg-gray-50 flex items-center justify-center">
                        <IconBot className="w-7 h-7 opacity-30 animate-pulse" />
                      </div>
                      <div className="flex gap-1.5 items-center py-2">
                        <span className="w-1.5 h-1.5 bg-gray-200 rounded-full animate-bounce"></span>
                        <span className="w-1.5 h-1.5 bg-gray-200 rounded-full animate-bounce delay-150"></span>
                        <span className="w-1.5 h-1.5 bg-gray-200 rounded-full animate-bounce delay-300"></span>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              <div className="px-6 pb-10 pt-4 bg-white">
                <form onSubmit={handleSendMessage} className="relative max-w-2xl mx-auto">
                  <div className="relative flex items-center bg-gray-50 border border-gray-100 rounded-[2.5rem] p-2 focus-within:bg-white focus-within:ring-2 focus-within:ring-[#FF6600]/10 transition-all shadow-sm">
                    <div className="relative flex-shrink-0">
                      <button 
                        type="button" 
                        onClick={() => setShowPlusMenu(!showPlusMenu)}
                        className={`w-12 h-12 flex items-center justify-center rounded-full transition-all ${showPlusMenu ? 'bg-black text-white' : 'bg-[#FF6600] text-white hover:bg-black'}`}
                      >
                        <span className={`text-2xl transition-transform font-light ${showPlusMenu ? 'rotate-45' : ''}`}>+</span>
                      </button>
                      {showPlusMenu && (
                        <div className="absolute bottom-full left-0 mb-4 bg-white border border-gray-100 rounded-2xl shadow-xl p-2 min-w-[150px] animate-in fade-in slide-in-from-bottom-2">
                          <button 
                            onClick={() => {
                              setStep(AppStep.PDF_UPLOAD);
                              setShowPlusMenu(false);
                            }}
                            className="w-full text-left px-4 py-3 text-sm font-semibold hover:bg-gray-50 rounded-xl transition-colors flex items-center gap-3 text-gray-700"
                          >
                            <IconFileUp className="w-4 h-4 text-[#FF6600]" />
                            Cambia PDF
                          </button>
                        </div>
                      )}
                    </div>
                    <input 
                      type="text" 
                      value={inputValue}
                      onChange={(e) => setInputValue(e.target.value)}
                      placeholder="Scrivi un messaggio..."
                      className="flex-grow bg-transparent border-none outline-none px-4 md:px-6 py-4 text-[14px] md:text-[15px] text-gray-800 placeholder:text-gray-300 font-verdana"
                    />
                    <button 
                      type="submit"
                      disabled={!inputValue.trim() || isTyping}
                      className="text-[#FF6600] w-10 h-10 md:w-12 md:h-12 flex items-center justify-center flex-shrink-0 rounded-full hover:bg-[#FF6600]/10 disabled:opacity-10 transition-all"
                    >
                      <IconSend className="w-5 h-5 md:w-6 md:h-6" />
                    </button>
                  </div>
                  <p className="text-[6px] text-center text-gray-300 mt-4 tracking-[0.2em] uppercase font-bold px-4">
                    Qualsiasi sistema, per quanto sofisticato sia, può commettere errori e non può sostituirsi ad un attenta lettura del documento
                  </p>
                </form>
              </div>
            </div>
          )}

          {/* HOW IT WORKS STEP */}
          {step === AppStep.HOW_IT_WORKS && (
            <div className="flex-grow overflow-y-auto px-6 py-10 chat-scroll animate-in fade-in duration-700">
              <div className="max-w-4xl mx-auto space-y-12 pb-20">
                <div className="text-center mb-16">
                  <h1 className="text-4xl md:text-5xl font-black mb-4 font-outfit">Architettura <span className="text-[#FF6600]">GraphRAG</span></h1>
                  <p className="text-gray-500 font-light text-lg">Un sistema di recupero deterministico potenziato da orchestratori LLM.</p>
                </div>

                <div className="grid md:grid-cols-2 gap-8">
                  <div className="bg-white border border-gray-100 p-8 rounded-3xl shadow-sm hover:orange-glow transition-all">
                    <div className="bg-[#FF6600] text-white w-12 h-12 rounded-xl flex items-center justify-center mb-6">
                      <IconFileUp className="w-6 h-6" />
                    </div>
                    <h3 className="text-xl font-bold mb-3">Ingestion & Struttura</h3>
                    <p className="text-gray-600 font-light text-sm leading-relaxed">
                      Il PDF non viene solo "letto", ma processato per estrarre la <strong>gerarchia logica</strong>. Utilizziamo librerie specializzate per ricostruire tabelle, titoli e sezioni, garantendo che l'informazione non perda mai il suo contesto originale durante la scomposizione.
                    </p>
                  </div>

                  <div className="bg-white border border-gray-100 p-8 rounded-3xl shadow-sm hover:orange-glow transition-all">
                    <div className="bg-black text-white w-12 h-12 rounded-xl flex items-center justify-center mb-6">
                      <IconLayers className="w-6 h-6" />
                    </div>
                    <h3 className="text-xl font-bold mb-3">Chunking</h3>
                    <p className="text-gray-600 font-light text-sm leading-relaxed">
                      Applichiamo una strategia di <strong>chunking ricorsivo</strong>. Il testo viene diviso in frammenti ottimizzati per gli embedding, mantenendo sovrapposizioni intelligenti tra i paragrafi per non interrompere la coerenza semantica tra i nodi del database.
                    </p>
                  </div>

                  <div className="bg-white border border-gray-100 p-8 rounded-3xl shadow-sm hover:orange-glow transition-all">
                    <div className="bg-black text-white w-12 h-12 rounded-xl flex items-center justify-center mb-6">
                      <IconDatabase className="w-6 h-6" />
                    </div>
                    <h3 className="text-xl font-bold mb-3">Knowledge Graph (Neo4j)</h3>
                    <p className="text-gray-600 font-light text-sm leading-relaxed">
                      I chunk e le entità vengono mappati in <strong>Neo4j</strong>. Ogni frammento diventa un nodo collegato non solo vettorialmente, ma anche per relazione logica (es. "appartiene alla sezione X"). Questo permette una navigazione dei dati multimodale: semantica e a grafo.
                    </p>
                  </div>

                  <div className="bg-white border border-gray-100 p-8 rounded-3xl shadow-sm hover:orange-glow transition-all">
                    <div className="bg-black text-white w-12 h-12 rounded-xl flex items-center justify-center mb-6">
                      <IconWorkflow className="w-6 h-6" />
                    </div>
                    <h3 className="text-xl font-bold mb-3">LangGraph</h3>
                    <p className="text-gray-500 font-light text-sm leading-relaxed">
                      L'intero flusso è gestito da <strong>LangGraph</strong>. Un sistema a stati finiti che coordina i nodi di analisi, recupero e validazione. Questo garantisce che ogni query segua un percorso logico rigoroso prima di produrre un output.
                    </p>
                  </div>
                </div>

                <div className="bg-gray-50 border border-gray-100 p-10 rounded-[3rem] shadow-inner">
                  <div className="text-center mb-10">
                    <h3 className="text-2xl font-black mb-2 font-outfit">Recupero <span className="text-[#FF6600]">Ibrido & Intelligente</span></h3>
                    <p className="text-gray-500 text-sm font-light max-w-2xl mx-auto">
                      l'LLM agisce esclusivamente come Orchestratore Decisionale: analizza l'intento della domanda per determinare la rotta di recupero ottimale.                      </p>
                  </div>

                  <div className="grid md:grid-cols-2 gap-8">
                    <div className="space-y-6">
                      <div className="bg-white p-6 rounded-2xl shadow-sm border border-black/5">
                        <div className="flex items-center gap-3 mb-3">
                          <div className="bg-[#FF6600]/10 px-2 py-1 rounded md font-bold text-[#FF6600] text-[10px] uppercase">Routing</div>
                          <h4 className="font-bold text-sm">Mistral come Router Strategico</h4>
                        </div>
                        <p className="text-xs text-gray-600 leading-relaxed font-light">
                          Utilizziamo <strong>Mistral</strong> per decidere la via di recupero. Se la domanda contiene entità specifiche già mappate nel DB, Mistral formula una <strong>Query Cypher</strong> basata sulle NE estratte.
                        </p>
                      </div>
                      
                      <div className="bg-white p-6 rounded-2xl shadow-sm border border-black/5">
                        <div className="flex items-center gap-3 mb-3">
                          <div className="bg-black/5 px-2 py-1 rounded md font-bold text-gray-500 text-[10px] uppercase">Vector</div>
                          <h4 className="font-bold text-sm">Ricerca Vettoriale</h4>
                        </div>
                        <p className="text-xs text-gray-600 leading-relaxed font-light">
                          Il sistema attiva una ricerca vettoriale quando il router identifica quesiti di natura concettuale o descrittiva.
                        </p>
                      </div>
                    </div>

                    <div className="space-y-6">
                      <div className="bg-white p-6 rounded-2xl shadow-sm border border-black/5">
                        <div className="flex items-center gap-3 mb-3">
                          <div className="bg-[#FF6600]/10 px-2 py-1 rounded md font-bold text-[#FF6600] text-[10px] uppercase">Entities</div>
                          <h4 className="font-bold text-sm">Named Entity Extraction (GLiNER)</h4>
                        </div>
                        <p className="text-xs text-gray-600 leading-relaxed font-light">
                          Sfruttiamo GLiNER per identificare entità chiave (nomi, luoghi, termini tecnici) sia nel documento che nella domanda utente.
                        </p>
                      </div>

                      <div className="bg-white p-6 rounded-2xl shadow-sm border border-black/5">
                        <div className="flex items-center gap-3 mb-3">
                          <div className="bg-black/5 px-2 py-1 rounded md font-bold text-gray-500 text-[10px] uppercase">Rerank</div>
                          <h4 className="font-bold text-sm">Reranking-v2-m3</h4>
                        </div>
                        <p className="text-xs text-gray-600 leading-relaxed font-light">
                          I risultati grezzi del database vengono filtrati da un <strong>Cross-Encoder</strong>, nello specifico il modello BGE-Reranker-v2-m3.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="bg-white border border-gray-100 p-8 rounded-[3rem] shadow-sm hover:orange-glow transition-all max-w-2xl mx-auto">
                  <div className="flex flex-col items-center text-center">
                    <div className="bg-[#FF6600] text-white w-14 h-14 rounded-2xl flex items-center justify-center mb-6 shadow-lg shadow-[#FF6600]/20">
                      <IconGlobe className="w-8 h-8" />
                    </div>
                    <h3 className="text-2xl font-black mb-3 font-outfit">Ricerca Globale</h3>
                    <p className="text-gray-600 font-light text-sm leading-relaxed">
                      Se la ricerca vettoriale sul documento attivo produce uno score di pertinenza basso, il sistema attiva automaticamente una <strong>Ricerca globale</strong>.
                    </p>
                  </div>
                </div>

                <div className="flex flex-col items-center text-center max-w-2xl mx-auto space-y-6">
                  <div className="bg-[#FF6600] text-white w-16 h-16 rounded-2xl flex items-center justify-center shadow-lg shadow-[#FF6600]/20">
                    <IconBot className="w-10 h-10" />
                  </div>
                  <h3 className="text-2xl font-black font-outfit">Sintesi</h3>
                  <p className="text-gray-600 font-light leading-relaxed">
                    L'LLM finale non genera testo libero ma agisce esclusivamente da sintetizzatore: riceve i dati filtrati e produce una risposta ancorata a una fonte certa.
                  </p>
                </div>

                <div className="flex justify-center pt-10">
                  <button 
                    onClick={returnFromHowItWorks}
                    className="bg-black text-white px-12 py-5 rounded-2xl font-bold hover:bg-[#FF6600] transition-all shadow-xl active:scale-95"
                  >
                    Torna alla Chat
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Developer Footer */}
      {isInitialPage && (
        <div className="w-full mt-20 py-12 px-6 border-t border-gray-100 flex flex-col items-center gap-6 animate-in fade-in slide-in-from-bottom-4 duration-1000 bg-white">
          <div className="flex items-center gap-8">
            <a href="https://github.com/ValerioBotto" target="_blank" rel="noopener noreferrer" className="group flex flex-col items-center gap-2">
              <div className="p-3 bg-gray-50 rounded-xl group-hover:bg-black group-hover:text-white transition-all">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"></path><path d="M9 18c-4.51 2-5-2-7-2"></path></svg>
              </div>
              <span className="text-[10px] font-bold uppercase tracking-widest text-gray-400 group-hover:text-black">GitHub</span>
            </a>
            <a href="https://www.linkedin.com/in/valerio-botto-4844b2190/" target="_blank" rel="noopener noreferrer" className="group flex flex-col items-center gap-2">
              <div className="p-3 bg-gray-50 rounded-xl group-hover:bg-[#0077b5] group-hover:text-white transition-all">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"></path><rect width="4" height="12" x="2" y="9"></rect><circle cx="4" cy="4" r="2"></circle></svg>
              </div>
              <span className="text-[10px] font-bold uppercase tracking-widest text-gray-400 group-hover:text-[#0077b5]">LinkedIn</span>
            </a>
          </div>
          <div className="text-center">
            <p className="text-[10px] text-gray-300 font-black tracking-[0.4em] uppercase">
              Developed by <span className="text-black">Valerio Botto</span>
            </p>
          </div>
        </div>
      )}

      {(step !== AppStep.CHAT && step !== AppStep.HOW_IT_WORKS && !isInitialPage) && (
        <footer className="py-10 text-center border-t border-gray-50 bg-white">
          <p className="text-[10px] text-gray-300 font-black tracking-[0.4em] uppercase">
            &copy; 2024 RAG CHATBOT
          </p>
        </footer>
      )}
    </div>
  );
};

export default App;